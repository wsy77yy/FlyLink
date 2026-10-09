import csv, hashlib, io, ipaddress, json, mimetypes, secrets, socket
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from functools import wraps
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction, OperationalError
from django.http import JsonResponse, FileResponse, HttpResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from .models import Profile, Record, Event, Attachment, Message, Notice, Config

KINDS = {'task','device','rental','job','application','ticket','invoice','withdrawal'}
SCENES = ['工业巡检','工程测绘','文旅航拍','农业植保','应急巡查']
STATES = {'pending':'待审核','open':'待接单','accepted':'飞行准备','declared':'计划待复核','ready':'待作业','working':'作业中','submitted':'待验收','rework':'待整改','settlement':'待结算','settled':'待互评','completed':'已完成','paused':'异常中止','cancel_requested':'取消待处理','cancelled':'已取消','available':'可租','unavailable':'已下架','payment':'待付款核对','renting':'使用中','returning':'归还验机中','closed':'已关闭','applied':'已投递','interview':'面试中','offered':'待双方确认','hired':'已入职','rejected':'已退回','processing':'处理中','resolved':'已解决'}

class Problem(Exception):
    def __init__(self, message, code=400): self.message, self.code = message, code

def ensure(ok, msg, code=400):
    if not ok: raise Problem(msg, code)

def api(fn):
    @wraps(fn)
    def wrapped(request, *args, **kwargs):
        try:
            if not request.user.is_authenticated: raise Problem('请先登录',401)
            return fn(request,*args,**kwargs)
        except Problem as e: return JsonResponse({'error':e.message},status=e.code)
        except (Record.DoesNotExist, User.DoesNotExist, Profile.DoesNotExist, Attachment.DoesNotExist): return JsonResponse({'error':'记录不存在或不可访问'},status=404)
        except (ValueError, KeyError, InvalidOperation, json.JSONDecodeError): return JsonResponse({'error':'输入格式不正确，请检查日期、金额和必填项'},status=400)
        except OperationalError: return JsonResponse({'error':'当前操作繁忙，请刷新后重试；未确认的变更不会保存'},status=409)
    return wrapped

def body(request):
    ensure(request.method=='POST','请使用 POST 提交',405)
    ensure(len(request.body)<200000,'提交内容过大')
    data=json.loads(request.body or b'{}')
    ensure(isinstance(data,dict),'输入必须为对象')
    return data

def text(d,key,required=False,limit=4000):
    value=str(d.get(key,'')).strip()
    ensure(not required or value, f'请填写{key}')
    ensure(len(value)<=limit,f'{key}内容过长')
    return value

def amount(value, minimum='0'):
    n=Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    ensure(n.is_finite() and Decimal(minimum)<=n<=Decimal('100000000'),'金额须为有效非负数且不超过一亿元')
    return str(n)

def day(value): return date.fromisoformat(str(value))
def now(): return timezone.now().isoformat()
def admin(u): return u.profile.role=='admin'
def isrole(u,role): ensure(u.profile.role==role,'当前身份没有此操作权限',403)
def verified(u): ensure(u.profile.verification=='approved','请先在资料与认证页面提交资料，并由运营审核通过',403)

def user_data(u, private=False):
    p=u.profile;d=p.data
    public={k:d.get(k,'') for k in ['name','city','skills','license','license_expiry','insurance_expiry','experience','bio','device','online']}
    return {'id':u.id,'username':u.username,'role':p.role,'verification':p.verification,'active':u.is_active,'data':d if private else public}

def eligible(u,r):
    p=u.profile;d=p.data;today=timezone.localdate()
    try:
        return p.verification=='approved' and u.is_active and d.get('online')=='idle' and day(d['license_expiry'])>=today and day(d['insurance_expiry'])>=today and r.data.get('scene') in d.get('skills',[]) and (r.data.get('license')!='CAAC-超视距' or d.get('license')=='CAAC-超视距') and not d.get('trainee',False)
    except (ValueError,KeyError,TypeError): return False

def participant(u,r):
    if admin(u) or u.id in (r.owner_id,r.assigned_id):return True
    if r.parent_id and r.kind in ['application','rental']: return r.parent.owner_id==u.id
    return False

def access(u,r):
    if participant(u,r):return True
    if r.kind=='task' and r.status=='open' and u.profile.role=='pilot':return eligible(u,r)
    if r.kind in ['device','job'] and r.status in ['available','open']:return True
    return False

def rec(r,u):
    full=participant(u,r)
    d=dict(r.data)
    if not full:
        for k in ['payment_ref','payment_received','settlement_ref','reviews','gates','plan','incident','cancel_reason','contract','acceptance','contact','note']:d.pop(k,None)
    return {'id':r.id,'number':f'FL{r.created_at:%Y%m%d}{r.id:05d}','kind':r.kind,'status':r.status,'status_label':STATES.get(r.status,r.status),'owner':r.owner_id,'assigned':r.assigned_id,'parent':r.parent_id,'owner_name':r.owner.profile.data.get('name',r.owner.username),'assigned_name':r.assigned.profile.data.get('name',r.assigned.username) if r.assigned_id else '', 'data':d,'version':r.version,'created_at':r.created_at.isoformat(),'updated_at':r.updated_at.isoformat()}

def notify(r, message, extra=None):
    ids={r.owner_id,r.assigned_id}
    if r.parent_id:ids.add(r.parent.owner_id)
    ids.update(extra or [])
    Notice.objects.bulk_create([Notice(user_id=i,record=r,text=message[:300]) for i in ids if i])

def log(u,r,action,detail=None):
    Event.objects.create(user=u,record=r,action=action,detail=detail or {})
    if r:notify(r,action)

def save(r):
    r.version+=1;r.save()

def attached(u,r,purpose):
    return Attachment.objects.filter(record=r,purpose=purpose).exists()

def gates(r,pilot=None):
    p=pilot or r.assigned;d=p.profile.data if p else {};today=timezone.localdate();g=r.data.get('gates',{})
    def valid_date(k):
        try:return day(d[k])>=today
        except (ValueError,KeyError,TypeError):return False
    license_ok=bool(p and p.profile.verification=='approved' and p.is_active and valid_date('license_expiry') and r.data.get('scene') in d.get('skills',[]) and not d.get('trainee',False) and (r.data.get('license')!='CAAC-超视距' or d.get('license')=='CAAC-超视距'))
    insurance_ok=bool(p and valid_date('insurance_expiry') and r.data.get('scene') in d.get('skills',[]))
    device_ok=bool(g.get('device_ref') and g.get('reviewed_by') and attached(p,r,'compliance'))
    air_ok=bool(g.get('airspace_ref') and g.get('reviewed_by') and g.get('airspace')=='approved')
    weather_ok=False
    try:
        measured=datetime.fromisoformat(g.get('weather_time','')); delta=timezone.now()-measured
        weather_ok=timedelta(0)<=delta<=timedelta(hours=3) and 0<=float(g['wind'])<=float(g['wind_limit']) and g.get('rain')=='no'
    except (TypeError,ValueError,KeyError):pass
    return [{'key':k,'label':label,'ok':ok,'detail':detail} for k,label,ok,detail in [('license','证照与授权',license_ok,'核验有效期、场景授权及执照等级'),('insurance','保险有效',insurance_ok,'运营按保单核对保障范围与有效期'),('device','设备登记',device_ok,g.get('device_ref') or '等待登记凭证与人工核验'),('airspace','空域条件',air_ok,g.get('airspace_ref') or '等待有效依据及人工核验'),('weather','天气检查',weather_ok,'须有近3小时的气象记录，且满足该机型限值')]]

def hardgate(r,pilot=None):
    failed=[g['label'] for g in gates(r,pilot) if not g['ok']]
    ensure(not failed,'暂不能继续：'+ '、'.join(failed)+'未通过')

def public(request):
    return JsonResponse({'csrf':get_token(request),'user':user_data(request.user,True) if request.user.is_authenticated else None})

def demo_access(request):
    """Return a phone-accessible LAN URL for local roadshow sessions."""
    ip = ''
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.connect(('8.8.8.8', 80))
            ip = client.getsockname()[0]
    except OSError:
        try: ip = socket.gethostbyname(socket.gethostname())
        except OSError: ip = ''
    try: is_lan = bool(ip and ipaddress.ip_address(ip).is_private)
    except ValueError: is_lan = False
    if not is_lan:
        return JsonResponse({'base_url': request.build_absolute_uri('/'), 'is_lan': False})
    port = request.get_port()
    authority = ip if port in ('80', '443') else f'{ip}:{port}'
    return JsonResponse({'base_url': f'{request.scheme}://{authority}/', 'is_lan': True})

def auth(request):
    try:
        d=body(request);mode=d.get('mode','login')
        if mode=='logout':logout(request);return JsonResponse({'ok':True})
        ip=request.META.get('REMOTE_ADDR','local');key='auth-'+ip
        ensure(cache.get(key,0)<25,'尝试次数过多，请十五分钟后重试',429)
        if mode=='register':
            username=text(d,'username',True,60);pwd=text(d,'password',True,128);role=d.get('role')
            ensure(role in ['enterprise','pilot'],'请选择需求方或飞手身份');ensure(len(pwd)>=10,'密码至少10位');ensure(d.get('agree') is True,'请确认用户协议与数据使用约定')
            ensure(not User.objects.filter(username=username).exists(),'账号已存在')
            with transaction.atomic():
                u=User.objects.create_user(username=username,password=pwd)
                Profile.objects.create(user=u,role=role,data={'name':text(d,'name',True,100),'online':'offline','skills':[], 'agreements_at':now()})
                log(u,None,'注册并同意服务与隐私约定')
        else:
            u=authenticate(request,username=d.get('username',''),password=d.get('password',''))
            if not u:cache.set(key,cache.get(key,0)+1,900);raise Problem('账号或密码不正确，或账号已停用',401)
        login(request,u);return JsonResponse({'user':user_data(u,True),'csrf':get_token(request)})
    except Problem as e:return JsonResponse({'error':e.message},status=e.code)

@api
def state(request):
    u=request.user
    records=Record.objects.select_related('owner__profile','assigned__profile','parent__owner').order_by('-id')
    visible=[rec(r,u) for r in records if access(u,r)]
    profiles=Profile.objects.select_related('user').all() if admin(u) else Profile.objects.select_related('user').filter(verification='approved',role='pilot',user__is_active=True)
    people=[user_data(p.user,admin(u)) for p in profiles]
    notices=list(Notice.objects.filter(user=u).order_by('-id')[:100].values('id','record_id','text','read','created_at'))
    config=Config.objects.filter(key='fees').first()
    return JsonResponse({'user':user_data(u,True),'records':visible,'people':people,'notices':notices,'config':config.data if config else {'rate':10},'server_time':now()})

@api
def profile(request):
    d=body(request);u=request.user;action=d.get('action','save')
    if action=='password':
        ensure(u.check_password(d.get('old','')),'原密码不正确');ensure(len(d.get('password',''))>=10,'新密码至少10位');u.set_password(d['password']);u.save();update_session_auth_hash(request,u);return JsonResponse({'ok':True})
    p=u.profile
    if action=='online':
        ensure(d.get('online') in ['idle','busy','offline'],'接单状态不正确');p.data={**p.data,'online':d['online']};p.save();return JsonResponse({'ok':True})
    fields=['name','city','contact','license','license_expiry','insurance_expiry','insurance_no','registration','device','experience','bio','company_no','education','projects']
    for k in fields:p.data[k]=text(d,k,False,3000 if k in ['bio','projects'] else 200)
    ensure(p.data['name'],'请填写企业或个人名称')
    p.data['skills']=[x for x in d.get('skills',[]) if x in SCENES];p.data['trainee']=bool(d.get('trainee',False))
    if p.role=='pilot':
        day(p.data['license_expiry']);day(p.data['insurance_expiry'])
    p.verification='pending';p.save();log(u,None,'更新资料并提交认证审核')
    Notice.objects.bulk_create([Notice(user=p.user,text=f'{u.username} 提交了认证申请') for p in Profile.objects.filter(role='admin')])
    return JsonResponse({'ok':True})

@api
def review_user(request,pk):
    ensure(admin(request.user),'仅运营可审核',403);d=body(request);p=Profile.objects.select_related('user').get(user_id=pk)
    ensure(p.role!='admin','不能从此处变更管理员',403)
    if d.get('action')=='disable':
        p.user.is_active=False;p.user.save();p.verification='rejected'
    elif d.get('action')=='enable':p.user.is_active=True;p.user.save();p.verification='pending'
    else:
        approved=d.get('decision')=='approved';reason=text(d,'reason',True)
        if approved:
            ensure(Attachment.objects.filter(owner=p.user,record__isnull=True).exists(),'用户尚未上传认证材料')
            if p.role=='pilot':
                ensure(day(p.data.get('license_expiry',''))>=timezone.localdate() and day(p.data.get('insurance_expiry',''))>=timezone.localdate(),'证照或保险已过期')
                ensure(p.data.get('skills') and p.data.get('registration'),'请先补全授权场景和设备登记号')
                ensure(not p.data.get('trainee'),'带教学员不可直接授予独立接单权限')
        p.verification='approved' if approved else 'rejected';p.data['review_reason']=reason;p.data['reviewed_at']=now()
    p.save();log(request.user,None,'用户审核',{'user':pk,'verification':p.verification});Notice.objects.create(user=p.user,text='认证状态更新：'+p.verification+'；'+p.data.get('review_reason',''))
    return JsonResponse({'ok':True})

@api
def create(request):
    d=body(request);u=request.user;kind=d.get('kind');ensure(kind in KINDS,'业务类型不正确');data={};assigned=None;parent=None;status='pending'
    with transaction.atomic():
        if kind=='task':
            isrole(u,'enterprise');verified(u)
            for k in ['title','scene','location','execute_time','quantity','requirements','acceptance','license','service']:data[k]=text(d,k,True)
            ensure(data['scene'] in SCENES,'场景不正确');ensure(data['service'] in ['pilot','bundle'],'请选择服务模式')
            data['budget']=amount(d.get('budget'),'.01');data['lat']=float(d['lat']);data['lng']=float(d['lng']);ensure(-90<=data['lat']<=90 and -180<=data['lng']<=180,'坐标范围不正确')
            ensure(datetime.fromisoformat(data['execute_time'])>datetime.now(),'执行时间必须晚于当前时间')
            data['urgent']=bool(d.get('urgent'));data['airspace_type']=text(d,'airspace_type',True);data['payment_received']=False;data['gates']={}
            rate=Config.objects.filter(key='fees').first();data['fee_rate']=rate.data.get('rate',10) if rate else 10
            data['device_requirement']=text(d,'device_requirement')
        elif kind=='device':
            verified(u)
            for k in ['title','city','model','registration','specs','accessories']:data[k]=text(d,k,True)
            for k in ['daily_price','deposit']:data[k]=amount(d.get(k),'.01')
            data['description']=text(d,'description');data['condition']='待核验'
        elif kind=='rental':
            verified(u);parent=Record.objects.get(pk=d['device'],kind='device');ensure(parent.status=='available','设备尚不可租')
            start=day(d['start']);end=day(d['end']);ensure(start>=timezone.localdate() and end>=start,'租期日期不正确')
            conflicts=Record.objects.filter(kind='rental',parent=parent).exclude(status__in=['cancelled','settled'])
            ensure(not any(day(x.data['start'])<=end and day(x.data['end'])>=start for x in conflicts),'此设备在所选租期已有预约，请更换日期')
            ensure(parent.owner_id!=u.id,'不可租赁自己上架的设备')
            data={'title':parent.data['title'],'start':str(start),'end':str(end),'delivery':text(d,'delivery',True),'days':(end-start).days+1,'rent':amount(Decimal(parent.data['daily_price'])*((end-start).days+1)),'deposit':parent.data['deposit'],'address':text(d,'address',True)};assigned=parent.owner;status='payment'
        elif kind=='job':
            isrole(u,'enterprise');verified(u)
            for k in ['title','city','description','license','job_type']:data[k]=text(d,k,True)
            data['salary_min']=amount(d['salary_min']);data['salary_max']=amount(d['salary_max']);ensure(Decimal(data['salary_max'])>=Decimal(data['salary_min']),'薪资上限不能低于下限')
        elif kind=='application':
            isrole(u,'pilot');verified(u);parent=Record.objects.get(pk=d['job'],kind='job');ensure(parent.status=='open','岗位已关闭');ensure(not Record.objects.filter(kind=kind,parent=parent,owner=u).exists(),'已投递此岗位')
            assigned=parent.owner;status='applied';data={'title':parent.data['title'],'cover':text(d,'cover'),'signatures':{}}
        elif kind=='ticket':
            parent=Record.objects.get(pk=d['parent']) if d.get('parent') else None
            ensure(not parent or participant(u,parent),'不能关联他人的订单',403)
            data={'title':text(d,'title',True),'description':text(d,'description',True),'category':text(d,'category',True)}
        elif kind in ['invoice','withdrawal']:
            parent=Record.objects.get(pk=d['parent'],kind='task');ensure(participant(u,parent),'无权访问该订单',403);ensure(parent.status in ['settled','completed'],'订单结算后才可申请')
            ensure(not Record.objects.filter(kind=kind,parent=parent,owner=u).exists(),'此订单已有申请')
            if kind=='invoice':ensure(u.id==parent.owner_id,'仅需求方可申请发票',403)
            else:ensure(u.id==parent.assigned_id,'仅飞手可申请对账',403)
            data={'title':text(d,'title',True),'description':text(d,'description',True),'amount':parent.data['budget']}
        r=Record.objects.create(kind=kind,owner=u,assigned=assigned,parent=parent,status=status,data=data);log(u,r,'创建'+{'task':'飞行任务','job':'招聘岗位','device':'设备档案','rental':'租赁订单','application':'求职申请','ticket':'客服工单','invoice':'开票申请','withdrawal':'对账申请'}[kind]);notify(r,'有新业务待审核',[p.user_id for p in Profile.objects.filter(role='admin')])
    return JsonResponse({'record':rec(r,u)})

@api
def detail(request,pk):
    u=request.user;r=Record.objects.select_related('owner__profile','assigned__profile','parent').get(pk=pk);ensure(access(u,r),'无权查看此记录',403);full=participant(u,r)
    files=list(Attachment.objects.filter(record=r).values('id','name','size','purpose','sha256','created_at','owner_id')) if full else []
    messages=list(Message.objects.filter(record=r).order_by('id').values('id','sender_id','sender__username','text','created_at')) if full else []
    events=list(Event.objects.filter(record=r).order_by('-id').values('id','user__username','action','detail','created_at')) if full else []
    candidates=[]
    if r.kind=='task' and full and (u.id==r.owner_id or admin(u)):
        candidates=[user_data(p.user) for p in Profile.objects.select_related('user').filter(role='pilot',verification='approved') if eligible(p.user,r)]
    return JsonResponse({'record':rec(r,u),'files':files,'messages':messages,'events':events,'gates':gates(r,u if u.profile.role=='pilot' and not r.assigned_id else None) if r.kind=='task' else [],'candidates':candidates})

@api
def action(request,pk):
    d=body(request);u=request.user;a=d.get('action')
    with transaction.atomic():
        r=Record.objects.select_for_update().select_related('parent__owner','owner__profile','assigned__profile').get(pk=pk)
        ensure(access(u,r),'无权操作此记录',403)
        ensure(d.get('version')==r.version,'记录已更新，请刷新后再操作',409)
        owner=u.id==r.owner_id;worker=u.id==r.assigned_id;operator=admin(u)
        note=text(d,'note')
        if a=='message':
            ensure(participant(u,r),'仅参与方可以发送消息',403);msg=text(d,'text',True,4000);Message.objects.create(record=r,sender=u,text=msg);notify(r,'有新的业务沟通消息');return JsonResponse({'ok':True})
        if r.kind=='task':
            if a=='review':
                ensure(operator and r.status=='pending','当前不可审核',403);ensure(note,'请填写审核意见');r.status='open' if d.get('approved') else 'rejected';r.data['review_note']=note
            elif a=='resubmit':
                ensure(owner and r.status=='rejected','当前不可重新提交',403);ensure(note,'请说明补充或修改内容');r.data['requirements']+='\n补充：'+note;r.status='pending'
            elif a=='gates':
                ensure(operator and r.status not in ['completed','cancelled'],'仅运营可核验',403);ensure(attached(u,r,'compliance'),'请先上传空域、设备或天气等核验依据，文件类型选择“合规凭证”')
                ensure(d.get('airspace') in ['approved','pending','blocked'],'空域状态不正确');wind=float(d['wind']);limit=float(d['wind_limit']);ensure(0<=wind<=100 and 0<limit<=50,'风速或机型限值不正确')
                r.data['gates']={'device_ref':text(d,'device_ref',True),'airspace_ref':text(d,'airspace_ref',True),'airspace':d['airspace'],'wind':wind,'wind_limit':limit,'rain':d.get('rain'),'weather_time':now(),'reviewed_by':u.username,'note':text(d,'note',True)}
            elif a=='invite':
                ensure((owner or operator) and r.status=='open','当前不可邀约',403);p=User.objects.get(pk=d['pilot']);ensure(eligible(p,r),'飞手资质或接单状态不满足要求');r.data['invited']=p.id;Notice.objects.create(user=p,record=r,text='您收到一项任务邀约，请核对要求后接单')
            elif a=='claim':
                isrole(u,'pilot');ensure(r.status=='open' and not r.assigned_id,'订单已被承接或状态变化',409);ensure(eligible(u,r),'资质、授权或在线状态不满足要求');hardgate(r,u);r.assigned=u;r.status='accepted'
            elif a=='plan':
                ensure(worker and r.status in ['accepted','declared'],'当前不可提交计划',403);r.data['plan']=text(d,'plan',True);r.status='declared'
            elif a=='release':
                ensure(operator and r.status=='declared','当前不可放行复核',403);hardgate(r);ensure(note,'请填写复核意见');r.status='ready';r.data['release_note']=note
            elif a=='payment':
                ensure(operator and r.status not in ['cancelled','completed'],'仅财务核对人员可登记',403);ensure(not r.data.get('payment_received'),'已核对收款，不可重复登记',409);ensure(attached(u,r,'payment'),'请先上传付款凭证');r.data['payment_ref']=text(d,'reference',True);r.data['payment_received']=True;r.data['payment_at']=now()
            elif a=='start':
                ensure(worker and r.status=='ready','当前不可开始作业',403);hardgate(r);ensure(r.data.get('payment_received'),'尚未核对项目付款');ensure(d.get('checklist') is True,'请确认现场、电量及设备检查');r.data['checkin']={'time':now(),'note':text(d,'note',True)};r.status='working'
            elif a=='submit':
                ensure(worker and r.status in ['working','rework'],'当前不可提交成果',403);ensure(attached(u,r,'deliverable'),'请先上传成果文件');r.data['report']=text(d,'report',True);r.status='submitted'
            elif a=='accept':
                ensure(owner and r.status=='submitted','仅需求方可验收',403);ensure(d.get('checklist') is True,'请按约定确认验收指标');r.data['acceptance_note']=text(d,'note',True);r.status='settlement'
            elif a=='rework':
                ensure(owner and r.status=='submitted','当前不可退回整改',403);r.data['rework_note']=text(d,'note',True);r.status='rework'
            elif a=='settle':
                ensure(operator and r.status=='settlement','当前不可结算',403);ensure(r.data.get('payment_received'),'尚未核对付款');ensure(attached(u,r,'settlement'),'请上传实际结算凭证');r.data['settlement_ref']=text(d,'reference',True);r.data['settled_at']=now();total=Decimal(r.data['budget']);fee=total*Decimal(str(r.data['fee_rate']))/100;r.data['fee']=amount(fee);r.data['income']=amount(total-Decimal(r.data['fee']));r.status='settled'
            elif a=='review_service':
                ensure((owner or worker) and r.status in ['settled','completed'],'结算后由双方评价',403);rating=int(d['rating']);ensure(1<=rating<=5,'评分须为1—5');reviews=r.data.setdefault('reviews',{});ensure(str(u.id) not in reviews,'已评价，不可重复');reviews[str(u.id)]={'rating':rating,'text':text(d,'note',True),'time':now()};r.status='completed' if len(reviews)>=2 else 'settled'
            elif a=='pause':
                ensure((worker or owner or operator) and r.status in ['ready','working','accepted','declared'],'当前不可中止',403);r.data['before_pause']=r.status;r.data['incident']=text(d,'note',True);r.status='paused'
            elif a=='resume':
                ensure(operator and r.status=='paused','仅运营可复核恢复',403);hardgate(r);ensure(note,'请填写整改和复核依据');r.status=r.data.get('before_pause','accepted');r.data['resume_note']=note
            elif a=='cancel':
                ensure(owner and r.status in ['pending','rejected','open','accepted','declared','ready','paused'],'当前不可申请取消',403);r.data['cancel_reason']=text(d,'note',True);r.status='cancel_requested'
            elif a=='cancel_confirm':
                ensure(operator and r.status=='cancel_requested','当前不可确认取消',403);ensure(note,'请填写处理意见')
                if r.data.get('payment_received'):ensure(attached(u,r,'refund') and d.get('reference'),'已收款订单须上传退款凭证并登记流水号');r.data['refund_ref']=d['reference'];r.data['refunded_at']=now()
                r.status='cancelled';r.data['cancel_result']=note
            elif a=='reschedule':
                ensure(owner and r.status in ['pending','open','accepted','declared','ready'],'当前不可改期',403);t=text(d,'execute_time',True);ensure(datetime.fromisoformat(t)>datetime.now(),'请选择将来的时间');r.data['execute_time']=t;r.data['gates']={};r.status='accepted' if r.assigned_id else 'pending';r.data['reschedule_note']=text(d,'note',True)
            else:raise Problem('此操作不可用')
        elif r.kind=='device':
            if a=='review':
                ensure(operator and r.status=='pending','仅运营可审核设备',403);ensure(attached(u,r,'evidence'),'请上传设备登记和维保凭证');r.status='available' if d.get('approved') else 'rejected';r.data['review_note']=text(d,'note',True)
            elif a=='toggle':ensure(owner or operator,'无权操作',403);ensure(r.status in ['available','unavailable'],'请先完成设备审核');r.status='unavailable' if r.status=='available' else 'available'
            else:raise Problem('操作不可用')
        elif r.kind=='rental':
            if a=='payment':
                ensure(operator and r.status=='payment','仅运营可核对租赁款',403);ensure(attached(u,r,'payment'),'请上传付款凭证');r.data['payment_ref']=text(d,'reference',True);r.data['insurance_ref']=text(d,'insurance_ref',True);ensure(attached(u,r,'compliance'),'请上传租赁保险凭证');r.status='renting'
            elif a=='return':ensure(owner and r.status=='renting','当前不可申请归还',403);r.data['return_note']=text(d,'note',True);r.status='returning'
            elif a=='inspect':
                ensure(operator and r.status=='returning','当前不可验机',403);ensure(attached(u,r,'evidence'),'请上传验机记录');damage=Decimal(amount(d.get('damage',0)));ensure(damage<=Decimal(r.data['deposit']),'扣款不得超过押金，本页面超额损失须另建工单');r.data['damage']=str(damage);r.data['refund']=amount(Decimal(r.data['deposit'])-damage);r.data['inspection']=text(d,'note',True);r.data['refund_ref']=text(d,'reference',True);ensure(attached(u,r,'refund'),'请上传押金退还或零退款结清凭证');r.status='settled'
            elif a=='cancel':ensure(owner and r.status=='payment','仅未付款预约可取消',403);r.status='cancelled'
            else:raise Problem('操作不可用')
        elif r.kind=='job':
            if a=='review':ensure(operator and r.status=='pending','当前不可审核',403);r.status='open' if d.get('approved') else 'rejected';r.data['review_note']=text(d,'note',True)
            elif a=='close':ensure(owner or operator,'无权关闭岗位',403);r.status='closed'
            else:raise Problem('操作不可用')
        elif r.kind=='application':
            if a=='interview':ensure(worker and r.status in ['applied','interview'],'仅招聘企业可邀请',403);r.data['interview']=text(d,'note',True);r.status='interview'
            elif a=='offer':ensure(worker and r.status in ['applied','interview'],'当前不可录用',403);ensure(attached(u,r,'contract'),'请上传待确认的合同文件');r.data['offer']=text(d,'note',True);r.status='offered'
            elif a=='sign':ensure((owner or worker) and r.status=='offered','当前不可确认',403);r.data.setdefault('signatures',{})[str(u.id)]=now()
            elif a=='hire':ensure(worker and r.status=='offered','当前不可确认入职',403);ensure(len(r.data.get('signatures',{}))==2,'双方需先确认合同');r.status='hired';r.data['hired_at']=now()
            elif a=='reject':ensure(worker and r.status not in ['hired','rejected'],'当前不可操作',403);r.status='rejected';r.data['reason']=text(d,'note',True)
            else:raise Problem('操作不可用')
        elif r.kind in ['ticket','invoice','withdrawal']:
            ensure(operator,'仅运营可处理',403)
            if a=='process':r.status='processing';r.data['result']=text(d,'note',True)
            elif a=='resolve':
                if r.kind=='invoice':ensure(attached(u,r,'evidence'),'请上传实际发票文件')
                r.status='resolved';r.data['result']=text(d,'note',True)
            else:raise Problem('操作不可用')
        save(r);log(u,r,{'review':'完成业务审核','gates':'更新五项核验依据','claim':'飞手承接任务','plan':'提交飞行计划','release':'完成飞行准备复核','payment':'核对线下收款','start':'开始作业','submit':'提交作业成果','accept':'需求方验收通过','rework':'要求整改','settle':'登记实际结算','review_service':'提交履约评价','pause':'中止任务并上报异常','resume':'复核恢复任务','cancel':'提交取消申请','cancel_confirm':'完成取消处理','reschedule':'调整作业时间','invite':'邀约飞手','return':'申请设备归还','inspect':'完成验机与押金核对','sign':'确认合同内容','hire':'确认入职'}.get(a,a),{'note':note,'status':r.status})
    return JsonResponse({'record':rec(r,u)})

@api
def upload(request):
    ensure(request.method=='POST','使用POST上传',405);u=request.user;f=request.FILES.get('file');ensure(f,'请选择文件');ensure(0<f.size<=20*1024*1024,'单个文件须小于20 MB且非空')
    ext=Path(f.name).suffix.lower();ensure(ext in ['.pdf','.png','.jpg','.jpeg','.webp','.txt','.csv','.zip','.kml','.geojson','.mp4','.docx','.xlsx'],'不支持此文件格式')
    purpose=request.POST.get('purpose','evidence');ensure(purpose in ['evidence','payment','compliance','deliverable','settlement','refund','contract','track'],'文件用途不正确')
    r=Record.objects.get(pk=request.POST['record']) if request.POST.get('record') else None
    ensure(not r or participant(u,r),'不能上传到他人的业务记录',403)
    ensure(not r or r.status not in ['completed','cancelled'],'已归档记录不可新增文件')
    h=hashlib.sha256()
    for chunk in f.chunks():h.update(chunk)
    f.seek(0);name=Path(f.name).name[:190];f.name=secrets.token_hex(16)+ext
    obj=Attachment.objects.create(record=r,owner=u,file=f,name=name,purpose=purpose,size=f.size,sha256=h.hexdigest());log(u,r,'上传文件',{'name':name,'sha256':obj.sha256,'purpose':purpose})
    return JsonResponse({'id':obj.id,'name':name})

@api
def download(request,pk):
    f=Attachment.objects.select_related('record__parent').get(pk=pk);u=request.user
    ensure(admin(u) or (participant(u,f.record) if f.record else f.owner_id==u.id),'无权下载此文件',403)
    return FileResponse(f.file.open('rb'),as_attachment=True,filename=f.name,content_type='application/octet-stream')

@api
def profile_files(request,pk):
    ensure(admin(request.user) or request.user.id==pk,'无权查看认证文件',403)
    return JsonResponse({'files':list(Attachment.objects.filter(owner_id=pk,record__isnull=True).values('id','name','size','sha256','created_at'))})

@api
def notices(request):
    d=body(request);qs=Notice.objects.filter(user=request.user)
    if d.get('id'):qs=qs.filter(id=d['id'])
    qs.update(read=True);return JsonResponse({'ok':True})

@api
def config(request):
    ensure(admin(request.user),'仅管理员可配置',403);d=body(request);rate=float(d['rate']);ensure(0<=rate<=20,'费率应为0%—20%');Config.objects.update_or_create(key='fees',defaults={'data':{'rate':rate}});log(request.user,None,'更新新订单费率',{'rate':rate});return JsonResponse({'ok':True})

@api
def export(request,pk=None):
    u=request.user
    if pk:
        r=Record.objects.get(pk=pk);ensure(participant(u,r),'无权导出',403)
        payload={'record':rec(r,u),'events':list(Event.objects.filter(record=r).values('action','detail','created_at','user__username')),'files':list(Attachment.objects.filter(record=r).values('name','sha256','purpose','created_at')),'messages':list(Message.objects.filter(record=r).values('text','sender__username','created_at'))}
        result=JsonResponse(payload,json_dumps_params={'ensure_ascii':False,'indent':2});result['Content-Disposition']=f'attachment; filename="FlyLink-{pk}-archive.json"';return result
    stream=io.StringIO();writer=csv.writer(stream);writer.writerow(['编号','业务','状态','标题','金额','创建时间'])
    for r in Record.objects.select_related('owner','assigned','parent'):
        if participant(u,r):
            row=[r.id,r.kind,STATES.get(r.status,r.status),r.data.get('title',''),r.data.get('budget',r.data.get('rent','')),r.created_at.isoformat()]
            writer.writerow(["'"+str(x) if str(x).startswith(('=','+','-','@')) else x for x in row])
    response=HttpResponse('\ufeff'+stream.getvalue(),content_type='text/csv; charset=utf-8');response['Content-Disposition']='attachment; filename="FlyLink-records.csv"';return response

def page(request, path=''):
    if path.startswith('api/'):return JsonResponse({'error':'接口不存在'},status=404)
    root=settings.BASE_DIR/'web';target=(root/path).resolve()
    if path and target.is_relative_to(root.resolve()) and target.is_file():return FileResponse(target.open('rb'),content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
    return FileResponse((root/'index.html').open('rb'),content_type='text/html; charset=utf-8')
