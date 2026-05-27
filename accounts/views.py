from django.contrib.auth import logout
from django.contrib import messages

def logout_view(request):
    logout(request)
    # Consumir (vaciar) los mensajes
    list(messages.get_messages(request))
    return redirect('login')