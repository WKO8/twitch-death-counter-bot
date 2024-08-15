# Use uma imagem oficial do Python como base
FROM python:3.12-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo requirements.txt para o diretório de trabalho
COPY requirements.txt .

# Instala as dependências necessárias
RUN pip install --no-cache-dir -r requirements.txt

# Copia todos os arquivos da aplicação para o diretório de trabalho do contêiner
COPY . .

# Define a variável de ambiente para o Heroku reconhecer a porta
ENV PORT 5000

# Expor a porta que será utilizada pela aplicação
EXPOSE $PORT

# Comando para iniciar o servidor Flask
CMD ["python", "server_socket.py"]
