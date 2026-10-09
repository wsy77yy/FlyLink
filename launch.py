import os, sys, time, threading, webbrowser, secrets, socket
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
def lan_ip():
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as client:
            client.connect(('8.8.8.8',80));return client.getsockname()[0]
    except OSError:
        try:return socket.gethostbyname(socket.gethostname())
        except OSError:return ''
LAN_IP=lan_ip()
os.environ.setdefault('FLYLINK_BIND','0.0.0.0')
os.environ.setdefault('FLYLINK_HOSTS',','.join(x for x in ['127.0.0.1','localhost','testserver',LAN_IP] if x))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings')
os.environ.setdefault('PYTHONIOENCODING','utf-8')
import django
django.setup()
from django.core.management import call_command
from django.contrib.auth.models import User
from django.core.wsgi import get_wsgi_application
from core.models import Profile
from waitress import serve

def initialize():
    call_command('migrate',interactive=False,verbosity=0)
    if not User.objects.exists():
        credentials=[]
        for name,role,title in [('operator','admin','飞链运营管理员'),('enterprise','enterprise','需求方验收账户'),('pilot','pilot','飞手验收账户')]:
            pwd=secrets.token_urlsafe(12)
            u=User.objects.create_user(name,password=pwd,is_staff=role=='admin')
            Profile.objects.create(user=u,role=role,verification='approved' if role=='admin' else 'pending',data={'name':title,'online':'offline','skills':[]})
            credentials.append(f'{title}\n账号：{name}\n初始密码：{pwd}\n')
        (ROOT/'首次登录账号.txt').write_text('飞链首次登录账号（请妥善保管，登录后可在资料页修改密码）\n\n'+'\n'.join(credentials)+'\n初始需求方与飞手均未认证；请上传真实资料后由运营审核。\n',encoding='utf-8-sig')

if __name__=='__main__':
    import hashlib, urllib.request, json
    identity=hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    host=os.environ.get('FLYLINK_BIND','0.0.0.0')
    first=int(os.environ.get('FLYLINK_PORT','8870'))
    port=None
    for candidate in range(first,first+30):
        with socket.socket() as probe:
            occupied=probe.connect_ex(('127.0.0.1',candidate))==0
        if not occupied:
            port=candidate
            break
        try:
            info=json.load(urllib.request.urlopen(f'http://127.0.0.1:{candidate}/api/health',timeout=2))
            if info.get('build')=='desktop-20261002-r4' and info.get('instance')==identity:
                if '--no-browser' not in sys.argv:
                    webbrowser.open(f'http://127.0.0.1:{candidate}/?v=desktop-20261002-r4#home')
                sys.exit(0)
        except Exception:
            pass
    if port is None:
        print('没有可用端口，请关闭不使用的本地服务后重试。');sys.exit(1)
    initialize()
    print('FlyLink 飞链已启动');print(f'电脑访问：http://127.0.0.1:{port}');print(f'手机访问：http://{LAN_IP}:{port}' if LAN_IP else '未能识别局域网地址，请检查网络连接。');print('初始账号见软件目录内“首次登录账号.txt”。');print('关闭此窗口或按 Ctrl+C 停止服务。')
    if '--no-browser' not in sys.argv:
        threading.Timer(1.5,lambda:webbrowser.open(f'http://127.0.0.1:{port}/?v=desktop-20261002-r4#home')).start()
    serve(get_wsgi_application(),host=host,port=port,threads=6,max_request_body_size=25*1024*1024,ident='FlyLink')
