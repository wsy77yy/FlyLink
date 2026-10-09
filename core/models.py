from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20)
    verification = models.CharField(max_length=20, default='pending')
    data = models.JSONField(default=dict)

class Record(models.Model):
    kind = models.CharField(max_length=20, db_index=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='owned')
    assigned = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='assigned')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=30, db_index=True)
    data = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Event(models.Model):
    record = models.ForeignKey(Record, null=True, on_delete=models.PROTECT)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class Attachment(models.Model):
    record = models.ForeignKey(Record, null=True, on_delete=models.PROTECT)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    file = models.FileField(upload_to='evidence/%Y/%m')
    name = models.CharField(max_length=200)
    purpose = models.CharField(max_length=40, default='evidence')
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class Message(models.Model):
    record = models.ForeignKey(Record, on_delete=models.PROTECT)
    sender = models.ForeignKey(User, on_delete=models.PROTECT)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class Notice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    record = models.ForeignKey(Record, null=True, on_delete=models.PROTECT)
    text = models.CharField(max_length=300)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Config(models.Model):
    key = models.CharField(max_length=50, unique=True)
    data = models.JSONField(default=dict)
