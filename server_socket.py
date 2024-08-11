import sys, os, socket, json, logging
import time
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from emoji import demojize
import threading
import re
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app)

# URL Routing — Home Page
@app.route("/")
def index():
    return render_template('index.html')  # Usando um template para renderizar a página

# Função para iniciar a conexão com o Twitch
def startConnection():
    global data
    data = {
        "server": os.environ.get("TWITCH_SERVER"),
        "port": int(os.environ.get("TWITCH_PORT")),
        "nickname": os.environ.get("TWITCH_NICKNAME"),
        "token": os.environ.get("TWITCH_TOKEN"),
        "channel": os.environ.get("TWITCH_CHANNEL")
    }

    try:
        sock = socket.socket()
        sock.connect((data["server"], data["port"]))

        sock.send(f"PASS {data['token']}\n".encode('utf-8'))
        sock.send(f"NICK {data['nickname']}\n".encode('utf-8'))
        sock.send(f"JOIN {data['channel']}\n".encode('utf-8'))

        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s — %(message)s',
                            datefmt='%Y-%m-%d_%H:%M:%S',
                            handlers=[logging.FileHandler('chat.log', encoding='utf-8')])
        return sock
    except Exception as e:
        logging.error(f"Error starting connection: {e}")
        sys.exit(1)

@socketio.on('connect')
def handle_connect():
    socketio.emit('update_death_count', {'death_count': settings['death_count']})

# Função para monitorar as mensagens do Twitch
def getMessages():
    sock = startConnection()
    lenChannel = len(data["channel"]) + 2

    while True:
        resp = sock.recv(2048).decode('utf-8')
        match = re.search(r':(.*?!)', resp)
        startMessageIndex = resp.find(data["channel"]) + lenChannel
        message = resp[startMessageIndex:]

        if resp.startswith('PING'):
            sock.send("PONG\n".encode('utf-8'))
        elif len(resp) > 0:
            logging.info(demojize(resp))

        if match:
            user = match.group(1).strip(':!')
            settings['username_and_message'].append([user, message.strip()])
        else:
            print("Nenhum usuário encontrado")
        
        try:
            monitorMessage(settings['username_and_message'].index([user, message.strip()]), sock)
        except ValueError:
            print("Falha ao encontrar a mensagem")

# Função para monitorar e atualizar a contagem de deaths
def monitorMessage(index, sock):
    global settings
    message = settings['username_and_message'][index][1];

    splittedMessage = message.split(" ")

    settings['args'] = []

    for arg in splittedMessage:
        settings["args"].append(arg)

    cmd = settings['args'][0];

    if cmd in commands:
        commands[cmd](index, sock)
    else:
        print("Comando não encontrado")

# Função para enviar mensagem no chat da Twitch
def sendMessage(sock, message):
    """
    Envia uma mensagem para o chat da Twitch.
    :param sock: O socket conectado ao servidor da Twitch.
    :param message: A mensagem a ser enviada.
    """
    messageTemp = f"PRIVMSG {data['channel']} :{message}\n"
    sock.send(messageTemp.encode('utf-8'))

# Função para salvar as configurações de forma persistente
def save_settings():
    settings['args'] = []
    with open('settings_state.json', 'w') as f:
        json.dump(settings, f)
    f.close()

# Função para carregar as configurações de forma persistente
def load_settings():
    global settings
    try:
        with open('settings_state.json', 'r') as f:
            settings = json.load(f)
            settings['time_message_sent'] = 0
        f.close()
    except FileNotFoundError:
        pass

# ==========
#  COMANDOS
# ==========

# Função para incrementar o contador (global)
def increment_counter_global(idx, sock):
    currentTime = time.time();
    username = settings['username_and_message'][idx][0]
    end_of_timeout = currentTime - settings['time_message_sent'] >= int(settings['cooldown'])

    if end_of_timeout:
        settings['time_message_sent'] = time.time()
        settings['death_count'] += 1
        save_settings()
        print(f"Mensagem de morte detectada, enviada por {username}")
        print(f"Deaths: {settings['death_count']}")
        socketio.emit('update_death_count', {'death_count': settings['death_count']})  # Emite o evento de atualização

# Função para decrementar o contador (mods)
def decrement_counter_mods(idx, sock):
    username = settings['username_and_message'][idx][0]

    if username in settings['mods']:
        settings['death_count'] -= 1
        save_settings()
        print(f"Mensagem de decrementar contador detectada, enviada por {username}")
        print(f"Deaths: {settings['death_count']}")
        socketio.emit('update_death_count', {'death_count': settings['death_count']})  # Emite o evento de atualização

# Função para atualizar o contador (mods)
def update_counter_mods(idx, sock):
    username = settings['username_and_message'][idx][0]
    if username in settings['mods'] and len(settings['args']) == 2 and settings['args'][1].isnumeric():
        settings['death_count'] = int(settings['args'][1])
        save_settings()
        print(f"Mensagem de atualizar contador detectada, enviada por {username}")
        print(f"Deaths: {settings['death_count']}")
        socketio.emit('update_death_count', {'death_count': settings['death_count']})  # Emite o evento de atualização
    else:
        print("Usuário sem permissão ou argumentos inválidos");

# Função para atualizar o cooldown (mods)
def update_cooldown(idx, sock):
    username = settings['username_and_message'][idx][0]
    if username in settings['mods'] and len(settings['args']) == 2 and settings['args'][1].isnumeric():
        settings['cooldown'] = settings['args'][1]
        save_settings()
        print(f"Mensagem de atualizar cooldown detectada, enviada por {username}")
        print(f"Cooldown: {settings['cooldown']}")
        socketio.emit('update_death_count', {'death_count': settings['death_count']})  # Emite o evento de atualização
    else:
        sendMessage(sock, "Usuário sem permissão ou argumentos inválidos")
        print("Usuário sem permissão ou argumentos inválidos");

# Função para adicionar moderadores (host)
def add_mods(idx, sock):
    username = settings['username_and_message'][idx][0]
    if username == data['channel'].replace("#", "") and len(settings['args']) >= 2:
        for arg in settings['args'][1:]:
            if (arg.isnumeric() == True):
                continue
            elif arg in settings['mods']:
                continue
            else:
                settings['mods'].append(arg)
        save_settings()
        print(f"Mensagem de adicionar moderadores detectada, enviada por {username}")
    else:
        sendMessage(sock, "Usuário sem permissão ou argumentos inválidos")
        print("Usuário sem permissão ou argumentos inválidos");

# Função para remover moderadores (host)
def remove_mods(idx, sock):
    username = settings['username_and_message'][idx][0]
    if username == data['channel'].replace("#", "") and len(settings['args']) >= 2:
        for arg in settings['args'][1:]:
            if arg not in settings['mods']:
                continue
            else:
                settings['mods'].remove(arg)
        save_settings()
        print(f"Mensagem de adicionar moderadores detectada, enviada por {username}")
    else:
        sendMessage(sock, "Usuário sem permissão ou argumentos inválidos")
        print("Usuário sem permissão ou argumentos inválidos");

# Função para mostrar os moderadores (host)
def show_mods(idx, sock):
    username = settings['username_and_message'][idx][0]
    if username == data['channel'].replace("#", ""):
        print(f"Mensagem de adicionar moderadores detectada, enviada por {username}")
        sendMessage(sock, f"Mods: {', '.join(settings['mods'])}")
        print(f"Mods: {settings['mods']}")
    else:
        sendMessage(sock, "Usuário sem permissão ou argumentos inválidos")
        print("Usuário sem permissão ou argumentos inválidos");


# Objeto global de configurações
settings = {
    "args": [],
    "death_count": 0,
    "cooldown": 0,
    "time_message_sent": 0,
    "username_and_message": [],
    "mods": [],
}

commands = {
    "+morreu": increment_counter_global,
    "-morreu": decrement_counter_mods,
    "=morreu": update_counter_mods,
    "+mods": add_mods,
    "-mods": remove_mods,
    "=mods": show_mods,
    "=cooldown": update_cooldown, 
}

# Main Function
if __name__ == "__main__":
    load_settings()  # Carrega as configurações ao iniciar o servidor

    # Inicia a thread para monitorar o chat do Twitch
    twitch_thread = threading.Thread(target=getMessages)
    twitch_thread.daemon = True
    twitch_thread.start()

    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 8000)), debug=True)
