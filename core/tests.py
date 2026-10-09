import json, tempfile, shutil
from datetime import timedelta
from unittest.mock import MagicMock, patch
from django.test import TestCase, override_settings, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from .models import Profile, Record, Attachment, Event

class WorkflowTests(TestCase):
    def setUp(self):
        self.tmp=tempfile.mkdtemp(prefix='flylink-test-')
        self.override=override_settings(MEDIA_ROOT=self.tmp);self.override.enable()
        self.addCleanup(self.override.disable);self.addCleanup(lambda:shutil.rmtree(self.tmp))
        self.users={};self.clients={}
        for role in ['admin','enterprise','pilot','other']:
            u=User.objects.create_user(role,password='Test-password-2026')
            Profile.objects.create(user=u,role='pilot' if role=='other' else role,verification='approved',data={'name':role,'online':'idle','skills':['工业巡检'],'license':'CAAC-超视距','license_expiry':'2099-12-31','insurance_expiry':'2099-12-31','registration':'TEST-001'})
            self.users[role]=u;c=Client();c.force_login(u);self.clients[role]=c
    def post(self,who,path,d):return self.clients[who].post(path,json.dumps(d),content_type='application/json')
    def create(self,kind='task',who='enterprise',**kw):
        data={'kind':kind,'title':'测试厂区巡检','scene':'工业巡检','location':'大连测试厂区','execute_time':(timezone.now()+timedelta(days=2)).replace(tzinfo=None).isoformat(),'quantity':'10点位','requirements':'完成巡检','acceptance':'点位完整影像清晰','license':'CAAC-视距内','service':'bundle','budget':'1000','lat':38.9,'lng':121.6,'airspace_type':'unknown'};data.update(kw)
        res=self.post(who,'/api/records',data);self.assertEqual(res.status_code,200,res.content);return Record.objects.get(pk=res.json()['record']['id'])
    def act(self,who,r,a,code=200,**kw):
        r.refresh_from_db();res=self.post(who,f'/api/records/{r.id}/action',{'version':r.version,'action':a,**kw});self.assertEqual(res.status_code,code,res.content);r.refresh_from_db();return res
    def upload(self,who,r,purpose='evidence'):
        res=self.clients[who].post('/api/upload',{'record':str(r.id) if r else '','purpose':purpose,'file':SimpleUploadedFile('evidence.txt',b'acceptance test evidence',content_type='text/plain')});self.assertEqual(res.status_code,200,res.content);return res.json()['id']
    def ready(self):
        r=self.create();self.act('admin',r,'review',approved=True,note='核对任务资料');self.upload('admin',r,'compliance');self.act('admin',r,'gates',device_ref='TEST-001',airspace_ref='MANUAL-001',airspace='approved',wind=2,wind_limit=6,rain='no',note='仅测试数据，不是实际审批');self.act('pilot',r,'claim');self.act('pilot',r,'plan',plan='测试飞行计划');self.act('admin',r,'release',note='检查通过');return r
    def finish(self):
        r=self.ready();self.upload('enterprise',r,'payment');self.act('admin',r,'payment',reference='BANK-TEST');self.act('pilot',r,'start',checklist=True,note='现场检查完成');self.upload('pilot',r,'deliverable');self.act('pilot',r,'submit',report='交付完成');self.act('enterprise',r,'accept',checklist=True,note='按标准验收通过');self.upload('admin',r,'settlement');self.act('admin',r,'settle',reference='SETTLEMENT-TEST');return r
    def test_closed_loop_and_evidence(self):
        r=self.finish();self.assertEqual(r.status,'settled');self.assertEqual(r.data['income'],'900.00');self.act('enterprise',r,'review_service',rating=5,note='成果达标');self.act('pilot',r,'review_service',rating=5,note='协作顺畅');self.assertEqual(r.status,'completed');self.assertGreater(Event.objects.filter(record=r).count(),10);self.assertEqual(self.clients['enterprise'].get(f'/api/records/{r.id}/export').status_code,200)
    def test_five_gates_block_claim(self):
        r=self.create();self.act('admin',r,'review',approved=True,note='通过');self.act('pilot',r,'claim',400);self.assertIsNone(r.assigned_id)
    def test_expired_license_blocks_start(self):
        r=self.ready();self.upload('enterprise',r,'payment');self.act('admin',r,'payment',reference='BANK');p=self.users['pilot'].profile;p.data['license_expiry']='2020-01-01';p.save();self.act('pilot',r,'start',400,checklist=True,note='检查');self.assertEqual(r.status,'ready')
    def test_payment_required(self):
        r=self.ready();self.act('pilot',r,'start',400,checklist=True,note='检查完成')
    def test_unverified_cannot_publish(self):
        p=self.users['enterprise'].profile;p.verification='pending';p.save();res=self.post('enterprise','/api/records',{'kind':'task'});self.assertEqual(res.status_code,403)
    def test_no_cross_user_private_access(self):
        r=self.ready();aid=self.upload('enterprise',r);self.assertEqual(self.clients['other'].get(f'/api/records/{r.id}').status_code,403);self.assertEqual(self.clients['other'].get(f'/api/files/{aid}').status_code,403)
    def test_version_prevents_duplicate_action(self):
        r=self.create();v=r.version;self.act('admin',r,'review',approved=True,note='审核');res=self.post('admin',f'/api/records/{r.id}/action',{'version':v,'action':'review','approved':True,'note':'重复'});self.assertEqual(res.status_code,409)
    def test_financial_actions_restricted(self):
        r=self.ready();self.upload('enterprise',r,'payment');self.act('enterprise',r,'payment',403,reference='invalid')
    def test_stale_weather_blocks_start(self):
        r=self.ready();self.upload('enterprise',r,'payment');self.act('admin',r,'payment',reference='BANK');r.data['gates']['weather_time']=(timezone.now()-timedelta(hours=4)).isoformat();r.save();self.act('pilot',r,'start',400,checklist=True,note='check')
    def test_rework_and_pause(self):
        r=self.ready();self.upload('enterprise',r,'payment');self.act('admin',r,'payment',reference='BANK');self.act('pilot',r,'start',checklist=True,note='现场完成');self.act('pilot',r,'pause',note='现场临时施工');self.act('pilot',r,'submit',403,report='不可提交');self.act('admin',r,'resume',note='重新核验环境');self.upload('pilot',r,'deliverable');self.act('pilot',r,'submit',report='第一版');self.act('enterprise',r,'rework',note='补足遗漏点位');self.act('pilot',r,'submit',report='第二版');self.assertEqual(r.status,'submitted')
    def test_rental_closed_loop(self):
        dev=self.create('device','pilot',city='大连',model='测试机型',registration='D-001',specs='仅测试',accessories='电池2块',daily_price=200,deposit=1000);self.upload('pilot',dev);self.act('admin',dev,'review',approved=True,note='核验通过');start=str(timezone.localdate()+timedelta(days=1));end=str(timezone.localdate()+timedelta(days=2));r=self.create('rental',device=dev.id,start=start,end=end,delivery='自提',address='测试地址');self.assertEqual(r.data['rent'],'400.00');res=self.post('other','/api/records',{'kind':'rental','device':dev.id,'start':start,'end':end,'delivery':'自提','address':'测试'});self.assertEqual(res.status_code,400);self.upload('enterprise',r,'payment');self.upload('admin',r,'compliance');self.act('admin',r,'payment',reference='P',insurance_ref='I');self.act('enterprise',r,'return',note='已交回');self.upload('admin',r,'evidence');self.upload('admin',r,'refund');self.act('admin',r,'inspect',damage=0,reference='R',note='完好');self.assertEqual(r.status,'settled');self.assertEqual(r.data['refund'],'1000.00')
    def test_recruitment_closed_loop(self):
        job=self.create('job',city='大连',description='测试岗位',job_type='全职',salary_min=8000,salary_max=10000);self.act('admin',job,'review',approved=True,note='通过');a=self.create('application','pilot',job=job.id,cover='项目经历');self.act('enterprise',a,'interview',note='周一面试');self.upload('enterprise',a,'contract');self.act('enterprise',a,'offer',note='拟录用');self.act('enterprise',a,'sign');self.act('pilot',a,'sign');self.act('enterprise',a,'hire');self.assertEqual(a.status,'hired')
    def test_cancel_requires_refund_proof(self):
        r=self.ready();self.upload('enterprise',r,'payment');self.act('admin',r,'payment',reference='P');self.act('enterprise',r,'cancel',note='取消');self.act('admin',r,'cancel_confirm',400,note='退款',reference='R');self.upload('admin',r,'refund');self.act('admin',r,'cancel_confirm',note='已退',reference='R');self.assertEqual(r.status,'cancelled')
    def test_csrf_and_unauthenticated_access(self):
        c=Client(enforce_csrf_checks=True);self.assertEqual(c.get('/api/state').status_code,401);self.assertEqual(c.post('/api/auth',json.dumps({'mode':'login'}),content_type='application/json').status_code,403)
    def test_finance_idempotency_and_review_once(self):
        r=self.finish();self.act('admin',r,'settle',403,reference='duplicate');self.act('enterprise',r,'review_service',rating=5,note='完成');self.act('enterprise',r,'review_service',400,rating=5,note='重复');self.assertEqual(r.data['income'],'900.00')
    def test_user_review_requires_evidence(self):
        res=self.post('admin',f'/api/users/{self.users["pilot"].id}/review',{'decision':'approved','reason':'核实'});self.assertEqual(res.status_code,400);self.upload('pilot',None);res=self.post('admin',f'/api/users/{self.users["pilot"].id}/review',{'decision':'approved','reason':'核实'});self.assertEqual(res.status_code,200)

    @patch('core.views.socket.socket')
    def test_demo_access_returns_phone_accessible_home_url(self, socket_mock):
        client=MagicMock();client.getsockname.return_value=('192.168.10.25',54321)
        socket_mock.return_value.__enter__.return_value=client
        response=self.client.get('/api/demo-access',HTTP_HOST='127.0.0.1:8870',SERVER_PORT='8870')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{'base_url':'http://192.168.10.25:8870/','is_lan':True})
