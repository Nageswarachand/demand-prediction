FROM python:3.7


WORKDIR /MasterDataScience_FinalProject-master


COPY ./requirements.txt  /MasterDataScience_FinalProject-master

RUN pip install -r requirements.txt

RUN apt-get update && \
    apt-get install -y wget gnupg unzip && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    CHROME_DRIVER_VERSION=`curl -sS https://chromedriver.storage.googleapis.com/LATEST_RELEASE` && \
    wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/

COPY . .  


EXPOSE 8080
        

# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]

CMD ["streamlit","run","streamlit_app.py","--server.port","8080"]

