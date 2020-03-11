import os
import re
import requests
import time
import json
from xml.etree import ElementTree
import psycopg2
from psycopg2 import sql
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api import VkUpload
from vk_api.utils import get_random_id

# устанавливаем URL базы данных (для heroku оставить так)
DATABASE_URL = os.environ['DATABASE_URL']
# подключаемся к базе данных, таблице tokens, и получаем токен от группы вк
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cursor = conn.cursor()
cursor.execute('SELECT * FROM tokens LIMIT 1')
vktoken = cursor.fetchone()[1]
cursor.close()
conn.close()
# инициализируем сессию vkapi
session = requests.Session()
vk_session = vk_api.VkApi(token=vktoken)
longpoll = VkLongPoll(vk_session)
vk = vk_session.get_api()

# эта функция получает вопрос из базы и записывает его в БД, возвращает вопрос и раздатку-картинку (если есть)
# аргументы: 
# qtype - тип вопроса (чгк, свояк и т.д.), по умолчанию чгк; 
# date - с какой даты получать вопросы (чтобы отбросить разное а-ля чгк 90-х
def getquestion(event,qtype='1', date = '2010-01-01'):
    # собираем URL из аргументов
    url = 'https://db.chgk.info/xml/random/from_'+date+'/types'+qtype+'/limit1/'
    # получаем xml
    questionxml = requests.get(url)
    questionxml = ElementTree.fromstring(questionxml.content)
    # извлекаем из xml вопрос, ответ, комментарий, автора, зачет, источник, турнир
    question = questionxml.find('./question/Question').text.replace('\n',' ')
    if question != None:
        question = question.replace('\n',' ')
    answer = questionxml.find('./question/Answer').text.replace('\n',' ')
    if answer != None:
        answer = answer.replace('\n',' ')
    comment = questionxml.find('./question/Comments').text
    if comment != None:
        comment = comment.replace('\n',' ')
    author = questionxml.find('./question/Authors').text
    if author != None:
        author = author.replace('\n',' ')
    passcr = questionxml.find('./question/PassCriteria').text
    if passcr != None:
        passcr = passcr.replace('\n',' ')
    resource = questionxml.find('./question/Sources').text
    if resource != None:
        resource = resource.replace('\n',' ')
    tour = questionxml.find('./question/tournamentTitle').text
    if tour != None:
        tour = tour.replace('\n',' ')
    # получаем URL раздатки-картинки из вопроса и комментария если есть
    pic = None
    commentpic = None
    if re.search('\(pic: ',question) != None:
        question = re.split('\)',question, maxsplit = 1)
        pic = re.search('\d\d\d\d\d\d\d\d.jpg',question[0]).group(0)
        pic = 'https://db.chgk.info/images/db/' + pic
        question = question[1]
    if comment != None:
        if re.search('\(pic: ',comment) != None:
            comment = re.split('\)',comment, maxsplit = 1)
            commentpic = re.search('\d\d\d\d\d\d\d\d.jpg',comment[0]).group(0)
            commentpic = 'https://db.chgk.info/images/db/'+pic
            comment = comment[1]
    # текущее время
    currtime = int(time.time())
    # узнаем чат или диалог и записываем id
    if event.from_chat:
        ischat = True
        tabid = event.chat_id
    elif event.from_user:
        ischat = False
        tabid = event.user_id
    # по дефолту вопрос не отвечен))
    answered = False
    # записываем полученные данные в БД
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    values = (ischat, tabid, question, pic, answer, passcr, author, comment, commentpic, resource, tour, currtime, answered, question, pic, answer, passcr, author, comment, commentpic, resource, tour, currtime, answered)
    insert = ('INSERT INTO questions (ischat, tabid, question, pic, answer, pass, author, qcomments, commentpic, sources, tour, created, answered) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (ischat, tabid) DO UPDATE SET question = %s, pic = %s, answer = %s, pass = %s, author = %s, qcomments = %s, commentpic = %s, sources = %s, tour = %s, created = %s, answered = %s')
    cursor.execute(insert, values)
    conn.commit()
    cursor.close()
    conn.close()
    return question,pic

# эта функция посылает сообщение в чат ивента с текстом и картинкой из аргументов
def sendmessage(event,text,pic=None):
    if pic != None:
        upload = VkUpload(vk_session)
        image_url = pic
        image = session.get(image_url, stream=True)
        photo = upload.photo_messages(photos=image.raw)[0]
        attach='photo{}_{}'.format(photo['owner_id'], photo['id'])
        if event.from_user:
            vk.messages.send(
                user_id=event.user_id,
                random_id=get_random_id(),
                attachment=attach,
                message=text
                )
        elif event.from_chat:
            vk.messages.send(
                chat_id=event.chat_id,
                random_id=get_random_id(),
                attachment=attach,
                message=text
                )
    else:
        if event.from_user:
            vk.messages.send(
                user_id=event.user_id,
                random_id=get_random_id(),
                message=text
                )
        elif event.from_chat:
            vk.messages.send(
                chat_id=event.chat_id,
                random_id=get_random_id(),
                message=text
                )

# эта функция получает что-то (аргумет what = названию столбца БД) из БД
def getfromtab(event,what):
    if event.from_chat:
        ischat = True
        tabid = event.chat_id
    elif event.from_user:
        ischat = False
        tabid = event.user_id
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    values = (ischat,tabid)
    if what == 'question':
        insert = ('SELECT question FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'pic':
        insert = ('SELECT pic FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'answer':
        insert = ('SELECT answer FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'pass':
        insert = ('SELECT pass FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'author':
        insert = ('SELECT author FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'qcomments':
        insert = ('SELECT qcomments FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'commentpic':
        insert = ('SELECT commentpic FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'sources':
        insert = ('SELECT sources FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'tour':
        insert = ('SELECT tour FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'created':
        insert = ('SELECT created FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'answered':
        insert = ('SELECT answered FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'ischat':
        insert = ('SELECT ischat FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    elif what == 'tabid':
        insert = ('SELECT tabid FROM questions WHERE ischat = %s AND tabid = %s LIMIT 1')
    cursor.execute(insert, values)
    if cursor.rowcount()!=0:
        got = cursor.fetchone()[0]
    else: 
        got=None
    cursor.close()
    conn.close()
    return got

# эта функция проверяет ответ на правильность
def answercheck(event):
    answered = False
    answers = []
    # получаем ответ из БД
    answers.append(getfromtab(event,'answer'))
    # получаем зачет из бд
    passcr = getfromtab(event,'pass')
    # разбиваем зачет на отдельные варианты по , или ;
    if passcr != None:
        passcr = re.split('; |, ', passcr)
        for pass1 in passcr:
            answers.append(pass1)
    variations = []
    for i in range(len(answers)):
        answer = answers[i]
        # удаляем . " пробелы в начале, убираем все пробелы, переводим в ловеркейс
        answer = answer.strip('." ')
        answer = answer.replace(' ','')
        answer = answer.lower()
        # извлекаем все вариации из ответа (фигня в [])
        variations1 = re.findall('\[(.*?)\]',answer)
        for variation in variations1:
            variations.append(variation)
        # удаляем все вариации из ответа (фигня в [])
        answer = re.sub("[\[].*?[\]]", "",answer)
        answers[i] = answer
    # те же манипуляции с сообщением пользователя
    userans = event.text.split(' ',1)[1]
    userans = userans.strip('." ')
    userans = userans.replace(' ','')
    # удаляем все вариации из пользовательского ответа
    for variation in variations:
        userans = re.sub(variation, "",userans)
    # сравниваем ответ пользователя со всеми ответами
    for answer in answers:
        if userans == answer:
            answered = True
    # если ответ правильный, то обновляем соотв колонку в таблице и отправляем сообщение
    if answered == True:
        if event.from_chat:
            ischat = True
            tabid = event.chat_id
        elif event.from_user:
            ischat = False
            tabid = event.user_id
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()
        values = (ischat,tabid)
        insert = ('UPDATE questions SET answered = true WHERE ischat = %s AND tabid = %s')
        cursor.execute(insert, values)
        conn.commit()
        cursor.close()
        conn.close()
        sendmessage(event,'Ответ правильный!')
    
# ждем сообщений
for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
        # переводим сообщение в ловеркейс
        message = event.text.lower()
        if message.split(' ',1)[0] == 'вопрос':
            # определяем тип вопроса и дату, по умолчанию - чгк и 2010-01-01
            if 'чгк' in message.split(' '):
                qtype = '1'
            elif 'брейн' in message.split(' '):
                qtype = '2'
            elif 'инетрнет-турнир' in message.split(' '):
                qtype = '3'
            elif 'бескрылка' in message.split(' '):
                qtype = '4'
            elif 'cвояк' in message.split(' '):
                qtype = '5'
            elif 'эрудит-футбол' in message.split(' '):
                qtype = '6'
            else:
                qtype = '1'
            date = re.search('\d\d\d\d-\d\d-\d\d', message)
            if date != None:
                date = date.group(0)
            if date == None:
                date = '2010-01-01'
            # получаем вопрос, отправляем его сообщением
            question, pic = getquestion(event,qtype,date)
            sendmessage(event,question,pic)
        # пользователь просит ответ, помечаем вопрос как отвеченный и отправляем ответ и комментарий
        elif message == 'ответ':
            answer = getfromtab(event, 'answer')
            comment = getfromtab(event, 'qcomments')
            commentpic = getfromtab(event, 'commentpic')
            if event.from_chat:
                ischat = True
                tabid = event.chat_id
            elif event.from_user:
                ischat = False
                tabid = event.user_id
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            cursor = conn.cursor()
            values = (ischat,tabid)
            insert = ('UPDATE questions SET answered = true WHERE ischat = %s AND tabid = %s')
            cursor.execute(insert, values)
            conn.commit()
            cursor.close()
            conn.close()
            if answer != None:
                sendmessage(event,answer)
            if comment != None:
                sendmessage(event,comment,commentpic)
        # если вопрос отвечен, отправляем комментарий
        elif message == 'комментарий':
            answered = getfromtab(event,'answered')
            if answered == True:
                comment = getfromtab(event, 'qcomments')
                commentpic = getfromtab(event, 'commentpic')
                if comment != None:
                    sendmessage(event,comment,commentpic)
        # отправляем автора
        elif message == 'автор':    
            author = getfromtab(event,'author')
            if author != None:
                sendmessage(event,author)
        # если вопрос отвечен, отправляем источник
        elif message == 'источник':    
            answered = getfromtab(event,'answered')
            if answered == True:
                source = getfromtab(event,'sources')
                if '1.' in source:
                    source = re.split('\d\.',source)
                    while('' in source): 
                        source.remove('') 
                    source = "\n".join(source)
                if source != None:
                    sendmessage(event,source)
        # отправляем турнир
        elif message == 'турнир':    
            tour = getfromtab(event,'tour')
            if tour != None:
                sendmessage(event,tour)
        # если строка начинается с "о ", проверяем ответ (чтобы не читать весь спам из бесед, ибо лагать же будет)
        elif message.split(' ',1)[0] == 'о':
            answered = getfromtab(event,'answered')
            if answered == True:
                answercheck(event)       
