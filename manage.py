import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
from django.core.management import execute_from_command_line
if __name__ == '__main__': execute_from_command_line(sys.argv)
