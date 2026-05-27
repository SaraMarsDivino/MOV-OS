from django.db import models
from django.conf import settings

class Sucursal(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    direccion = models.CharField(max_length=500, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.nombre


class Conversation(models.Model):
    """Conversación privada por usuario (admin) para el asistente de reportes."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title or 'Conversation'} ({self.user.username})"


class Message(models.Model):
    SENDER_CHOICES = (("user", "user"), ("assistant", "assistant"), ("system", "system"))
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=16, choices=SENDER_CHOICES)
    text = models.TextField()
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)

    def __str__(self):
        return f"{self.sender}: {self.text[:60]}"

