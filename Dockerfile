FROM python:3

WORKDIR app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY trading_bot .

CMD [ "python", "./telegram_bot.py" ]
