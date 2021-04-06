import os
import re
import random
import requests
import time
import sched
import json
import difflib
from xml.etree import ElementTree
import psycopg2
from psycopg2 import sql
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api import VkUpload
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard

# устанавливаем URL базы данных (для heroku оставить так)
DATABASE_URL = os.environ['DATABASE_URL']
# подключаемся к базе данных, таблице tokens, и получаем токен от группы вк
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cursor = conn.cursor()
vkstring = ('vk',)
cursor.execute('SELECT * FROM tokens WHERE name = %s LIMIT 1', vkstring)
vktoken = cursor.fetchone()[1]
cursor.close()
conn.close()
# инициализируем сессию vkapi
session = requests.Session()
vk_session = vk_api.VkApi(token=vktoken)
vk = vk_session.get_api()

# эта функция получает вопрос из базы и записывает его в БД, возвращает вопрос и раздатку-картинку (если есть)
# аргументы: 
# qtype - тип вопроса (чгк, свояк и т.д.), по умолчанию чгк; 
# date - с какой даты получать вопросы (чтобы отбросить разное а-ля чгк 90-х
def getquestion(event,qtype='1', date = '2010-01-01', qset = None, search = None):
    # если игрок хочет получить вопрос через поиск
    if search != None:
        # получаем 1 вопрос по данному запросу
        url = 'https://db.chgk.info/xml/search/questions/from_'+date+'/types'+qtype+'/limit1/'+'"'+search+'"'
        questionxml = requests.get(url)
        questionxml = ElementTree.fromstring(questionxml.content)
        if questionxml.findall('./question/Question') == []:
            return 'Увы, по вашему запросу ничего не найдено.', None
        # узнаем, сколько всего вопросов
        qnumber = int(questionxml.find('./total').text)
        # база не позволяет получить больше 1000 вопросов
        if qnumber > 1000:
            qnumber = 1000
        # выбираем случайный вопрос
        qnumber = random.randint(0,qnumber-1)
        # получаем выбранный вопрос
        url = 'https://db.chgk.info/xml/search/questions/from_'+date+'/types'+qtype+'/limit1/"'+search+'"/?page='+str(qnumber)
        questionxml = requests.get(url)
        questionxml = ElementTree.fromstring(questionxml.content)
    # Если игрок хочет получить вопрос из школьного или студенческого пакета
    elif qset != None and qtype == '1':
        if qset == 'шк':
            file = open('school.txt', 'r')
        elif qset == 'студ':
            file = open('stud.txt', 'r')
        tours = file.readlines()
        qline = tours[random.randint(0,len(tours)-1)].split(' ')
        url = 'https://db.chgk.info/tour/'+qline[0]+'/xml'
        qnum = random.randint(1,int(qline[1].replace('\n','')))
        try:
            questionxml = requests.get(url)
        except:
            print(qline)
        questionxml = ElementTree.fromstring(questionxml.content)
        try:
            num1 = int(questionxml.find('question').find('Number').text)
        except:
            print(qline)
        qnum = qnum + num1 - 1
        for i in range(0,int(qline[1].replace('\n',''))):
            try:
                if int(questionxml.find('question').find('Number').text) != qnum:
                    questionxml.remove(questionxml.find('question'))
                else:
                    try:
                        questionxml.remove(questionxml.findall('question')[1])
                    except:
                        continue
            except:
                print(qline)
    # если игрок хочет получить случайный вопрос                
    else:
        # собираем URL из аргументов
        url = 'https://db.chgk.info/xml/random/from_'+date+'/types'+qtype+'/limit1/'
        # получаем xml
        questionxml = requests.get(url)
        questionxml = ElementTree.fromstring(questionxml.content)
        qnumber = 0
    # извлекаем из xml вопрос, ответ, комментарий, автора, зачет, источник, турнир
    if questionxml.find('./question/Question') != None:
        question = questionxml.find('./question/Question').text
        if question != None:
            question = question.replace('\n',' ')
        answer = questionxml.find('./question/Answer').text
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
        tour = questionxml.find('./question/tournamentTitle')
        if tour != None:
            tour = tour.text
        # Если в xml нет поля с названием турнира, значит это вопрос, взятый из пакета вручную (студ, шк) и надо его получить отдельно
        else:
            url = 'https://db.chgk.info/tour/'+'.'.join(qline[0].split('.')[0:-1])+'/xml'
            tourxml = requests.get(url)
            tourxml = ElementTree.fromstring(tourxml.content)
            tour = tourxml.find('Title')
            if tour != None:
                tour = tour.text
            else:
                if qline != None:
                    tour = '.'.join(qline[0].split('.')[0:-1])
        if tour != None:
            tour = tour.replace('\n',' ')
        # получаем URL раздатки-картинки из вопроса и комментария если есть
        pic = None
        commentpic = None
        if question != None:
            if '(pic: ' in question:
                pic = re.search('\(pic:.*?\)', question).group(0)
                question = re.sub(pic.replace('(', '\(').replace(')','\)'), '', question)
                pic = re.split(':',pic, maxsplit = 1)[1]
                pic = pic.strip('() ')
                if 'http' in pic:
                    pic = pic.strip(' ')
                else:
                    pic = re.search('\d\d\d\d\d\d\d\d\.\w\w\w',pic).group(0)
                    pic = 'https://db.chgk.info/images/db/' + pic
        if comment != None:
            if '(pic: ' in comment:
                commentpic = re.search('\(pic:.*?\)', comment).group(0)
                comment = re.sub(commentpic.replace('(', '\(').replace(')','\)'), '', comment)
                commentpic = re.split(':',commentpic, maxsplit = 1)[1]
                commentpic = commentpic.strip('() ')
                if 'http' in commentpic:
                    commentpic = commentpic.strip(' ')
                else:
                    commentpic = re.search('\d\d\d\d\d\d\d\d\.\w\w\w',commentpic).group(0)
                    commentpic = 'https://db.chgk.info/images/db/'+commentpic
        # текущее время
        currtime = int(time.time())
        # узнаем чат или диалог и записываем id
        tabid = event.obj.message['peer_id']
        # по дефолту вопрос не отвечен))
        answered = False
        # заменяем номера вопросов на &&&
        if qtype == '5':
            tag = re.search(' 10{0,1}\. ',question).group(0)
            qnum = int(re.search('1\d{0,1}',tag).group(0))
            question = question.replace(tag, '&&&'+str(qnum)+'. ', 1)
            answer = answer.replace(tag, '&&&'+' ', 1)
            if qnum == 10:
                ten = True
            else:
                ten = False
            for x in range(13):
                if ten == True:
                    qnum += 10
                else:
                    qnum +=1
                tag = ' '+str(qnum)+'. '
                if tag in answer.split('&&&')[-1]:
                    question = question.split('&&&')
                    answer = answer.split('&&&')
                    question[-1] = question[-1].replace(tag, ' &&&'+str(qnum)+'. ', 1)
                    answer[-1] = answer[-1].replace(tag, ' &&& ', 1)
                    question = '&&&'.join(question)
                    answer = '&&&'.join(answer)
        # записываем полученные данные в БД
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()
        values = (tabid, question, pic, answer, passcr, author, comment, commentpic, resource, tour, currtime, answered, qtype, question, pic, answer, passcr, author, comment, commentpic, resource, tour, currtime, answered, qtype)
        insert = ('INSERT INTO questions (tabid, question, pic, answer, pass, author, qcomments, commentpic, sources, tour, created, answered, qtype) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (tabid) DO UPDATE SET question = %s, pic = %s, answer = %s, pass = %s, author = %s, qcomments = %s, commentpic = %s, sources = %s, tour = %s, created = %s, answered = %s, qtype = %s')
        cursor.execute(insert, values)
        conn.commit()
        cursor.close()
        conn.close()
        # Если вопрос свояка, обрезаем его до вопроса за 10
        if qtype == '5':
            question = re.split('&&&', question)
            question = "\n".join((question[0],question[1]))
    else:
        question = None
        pic = None
    return question,pic

# эта функция посылает сообщение в чат ивента с текстом и картинкой из аргументов
def sendmessage(event,text,pic=None,kboard=None):
    if text != None and text.replace(' ', '') != '':
        if pic != None:
            # это на случай, если возникнет ошибка с загрузкой картинки. да, они иногда возникают, но очень редко
            try:
                upload = VkUpload(vk_session)
                image_url = pic
                image = session.get(image_url, stream=True)
                photo = upload.photo_messages(photos=image.raw)[0]
                attach='photo{}_{}'.format(photo['owner_id'], photo['id'])
                if kboard != None:
                    vk.messages.send(
                        peer_id = event.obj.message['peer_id'],
                        random_id=get_random_id(),
                        attachment=attach,
                        message=text,
                        keyboard=kboard
                        )
                else:
                    vk.messages.send(
                        peer_id = event.obj.message['peer_id'],
                        random_id=get_random_id(),
                        attachment=attach,
                        message=text
                        )
            except:
                print(pic)
                text = pic + ' ' + text
                pic = None
        if pic == None:
            if kboard != None:
                vk.messages.send(
                    peer_id = event.obj.message['peer_id'],
                    random_id=get_random_id(),
                    message=text,
                    keyboard=kboard
                    )
            else:
                vk.messages.send(
                    peer_id = event.obj.message['peer_id'],
                    random_id=get_random_id(),
                    message=text
                    )
  
# эта функция возвращает json-объект клавиатуры
def getkeyboard(answered):
    keyboard = VkKeyboard()
    # если игрок ответил на вопрос, предложить ему получить новый
    if answered == True:
        keyboard.add_button('Вопрос ЧГК','primary')
        keyboard.add_button('Вопрос свояк')
        keyboard.add_button('Вопрос брейн')
        keyboard.add_line()
        keyboard.add_button('Вопрос студ')
        keyboard.add_button('Вопрос шк')
        keyboard.add_line()
        keyboard.add_button('Источник')
        #keyboard.add_line()
        keyboard.add_button('Турнир')
        #keyboard.add_line()
        keyboard.add_button('Автор')
    # если игрок еще не ответил на вопрос, предложить получить ответ
    elif answered == False:
        keyboard.add_button('Ответ','primary')
        keyboard.add_line()
        keyboard.add_button('Турнир')
        keyboard.add_line()
        keyboard.add_button('Автор')
    keyboard = keyboard.get_keyboard()
    return keyboard

# эта функция получает что-то (аргумет what = названию столбца БД) из БД
def getfromtab(event,what):
    tabid = event.obj.message['peer_id']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    values = (tabid,)
    if what == 'question':
        insert = ('SELECT question FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'pic':
        insert = ('SELECT pic FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'answer':
        insert = ('SELECT answer FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'pass':
        insert = ('SELECT pass FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'qtype':
        insert = ('SELECT qtype FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'author':
        insert = ('SELECT author FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'qcomments':
        insert = ('SELECT qcomments FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'commentpic':
        insert = ('SELECT commentpic FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'sources':
        insert = ('SELECT sources FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'tour':
        insert = ('SELECT tour FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'created':
        insert = ('SELECT created FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'answered':
        insert = ('SELECT answered FROM questions WHERE tabid = %s LIMIT 1')
    elif what == 'tabid':
        insert = ('SELECT tabid FROM questions WHERE tabid = %s LIMIT 1')
    cursor.execute(insert, values)
    if cursor.rowcount != 0:
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
    # если вопрос свояка, берем первый ответ
    qtype = getfromtab(event,'qtype')
    if qtype == '5':
        answersi = answers[0]
        answersi = re.split('&&&', answersi)
        answersi = answersi[1].lower()
        answersi = answersi.replace('ё','е')
        # извлекаем критерии зачета
        if 'зачет' in answersi:
            answersi, passcrsi = re.split('зачет',answersi,maxsplit = 1)
            passcrsi = passcrsi.strip(':\]\}). ')
            passcrsi = re.split('; |, ', passcrsi)
            for pcr in passcrsi:
                answers.append(pcr)
        # удаляем информацию в скобочках
        answersi = re.sub("[\{(].*?[\})]", "",answersi)
        answers[0] = answersi
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
        answer = answer.replace('"','')
        answer = answer.replace(',','')
        answer = answer.replace('.','')
        answer = answer.replace(';','')
        answer = answer.lower()
        answer = answer.replace('ё','е')
        if 'незачет' in answer:
            answer = re.split('незачет',answer,maxsplit = 1)[0]
        # извлекаем все вариации из ответа (фигня в [])
        variations1 = re.findall('\[(.*?)\]',answer)
        for variation in variations1:
            variations.append(variation)
        # удаляем все вариации из ответа (фигня в [])
        answer = re.sub("[\[].*?[\]]", "",answer)
        answers[i] = answer
    # те же манипуляции с сообщением пользователя
    userans = event.obj.message['text'].lower()
    userans = userans.split(' ',1)[1]
    userans = userans.strip('." ')
    userans = userans.replace(' ','')
    userans = userans.replace('"','')
    userans = userans.replace(',','')
    userans = userans.replace('.','')
    userans = userans.replace(';','')
    userans = userans.replace('ё','е')
    # удаляем все вариации из пользовательского ответа
    for variation in variations:
        variation = variation.replace('[','').replace(']','').replace('(','').replace(')','')
        userans = re.sub(variation, "",userans)
    # сравниваем ответ пользователя со всеми ответами
    for answer in answers:
        if difflib.SequenceMatcher(None,userans,answer).ratio()>=0.7:
            answered = True
    # если ответ правильный, то обновляем соотв колонку в таблице и отправляем сообщение
    if answered == True:
        if qtype == '5':
            onsianswer(event,True)
        else:
            sendmessage(event,'Ответ правильный!',None,getkeyboard(True))
            comment = getfromtab(event, 'qcomments')
            commentpic = getfromtab(event, 'commentpic')
            if comment != None:
                sendmessage(event,comment,commentpic)
            tabid = event.obj.message['peer_id']
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            cursor = conn.cursor()
            values = (tabid,)
            insert = ('UPDATE questions SET answered = true WHERE tabid = %s')
            cursor.execute(insert, values)
            conn.commit()
            cursor.close()
            conn.close()
    elif answered == False:
        sendmessage(event,'Увы, ответ неправильный.')

# эта функция удаляет из вопроса своей игры вопрос и ответ текущего номинала, аргумент user == True, если игрок сам ответил на вопрос, а не попросил его
def onsianswer(event,user,answer=None):
    tabid = event.obj.message['peer_id']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    values = (tabid,)
    insert = ("UPDATE questions SET question = (SELECT REGEXP_REPLACE(question, '(&&&.*\s)+?&&&', '&&&')), answer = (SELECT REGEXP_REPLACE(answer, '(&&&.*\s)+?&&&', '&&&')) WHERE tabid = %s")
    cursor.execute(insert, values)
    conn.commit()
    cursor.close()
    conn.close()
    question = getfromtab(event,'question')
    if question != None:
        question = re.split('&&&', question)
    # после вопроса за 50 помечаем вопрос как отвеченный
    if 'done' in question:
        if user == True:
            sendmessage(event,'Ответ правильный!',None,getkeyboard(True))
        else:
            if answer != None:
                sendmessage(event,answer,None,getkeyboard(True))
        comment = getfromtab(event, 'qcomments')
        commentpic = getfromtab(event, 'commentpic')
        if comment != None:
            sendmessage(event,comment,commentpic)
        tabid = event.obj.message['peer_id']
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()
        values = (tabid,)
        insert = ('UPDATE questions SET answered = true WHERE tabid = %s')
        cursor.execute(insert, values)
        conn.commit()
        cursor.close()
        conn.close()
    # перед вопросом за 50 убираем текст вопроса иначе шлем вопрос следующего номинала
    elif len(question) == 2:
        if user == True:
            sendmessage(event,'Ответ правильный!')
        else:
            if answer != None:
                sendmessage(event,answer)
        question = "\n".join((question[0],question[1]))
        if question != None:
            sendmessage(event,question)
        tabid = event.obj.message['peer_id']
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()
        values = ('done',tabid)
        insert = ('UPDATE questions SET question = %s WHERE tabid = %s')
        cursor.execute(insert, values)
        conn.commit()
        cursor.close()
        conn.close()
    # иначе возвращаем текст вопроса
    else:
        if user == True:
            sendmessage(event,'Ответ правильный!')
        else:
            if answer != None:
                sendmessage(event,answer)
        question = "\n".join((question[0],question[1]))
        if question != None:
            sendmessage(event,question)
    

# ждем сообщений
while True:
    longpoll = VkBotLongPoll(vk_session, '177823701')
    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                # переводим сообщение в ловеркейс
                message = event.obj.message['text'].lower()
                message = message.replace('[club177823701|чгкрески] ','')
                message = message.replace('[club177823701|@chgkreski] ','')
                if message == 'начать':
                    sendmessage(event,"Сейчас бот отправит вам случайный вопрос ЧГК из Базы!\nВы можете попробовать ответить на него, отправив сообщение «о <ваш ответ>», например, «о Пушкин».\nЕсли захотите узнать ответ на вопрос, нажмите кнопку «Ответ» на клавиатуре или отправьте сообщение «ответ».\nУзнать больше о доступных командах можно здесь - https://vk.cc/ariwHL")
                    message = 'вопрос'
                if message.split(' ',1)[0] == 'вопрос':
                    # определяем тип вопроса и дату, по умолчанию - чгк и 2010-01-01
                    if 'чгк' in message.split(' '):
                        qtype = '1'
                        message = message.replace('чгк','',1)
                    elif 'брейн' in message.split(' '):
                        qtype = '2'
                        message = message.replace('брейн','',1)
                    elif 'интернет-турнир' in message.split(' '):
                        qtype = '3'
                        message = message.replace('интернет-турнир','',1)
                    elif 'бескрылка' in message.split(' '):
                        qtype = '4'
                        message = message.replace('бескрылка','',1)
                    elif 'свояк' in message.split(' '):
                        qtype = '5'
                        message = message.replace('свояк','',1)
                    elif 'эрудит-футбол' in message.split(' '):
                        qtype = '6'
                        message = message.replace('эрудит-футбол','',1)
                    else:
                        qtype = '1'
                    date = re.search('\d\d\d\d-\d\d-\d\d', message)
                    if date != None:
                        date = date.group(0)
                        message = re.sub('\d\d\d\d-\d\d-\d\d','' , message)
                    if date == None:
                        date = '2010-01-01'
                    if 'шк' in message.split(' '):
                        qset = 'шк'
                        message = message.replace('шк','',1)
                    elif 'студ' in message.split(' '):
                        qset = 'студ'
                        message = message.replace('студ','',1)
                    else:
                        qset = None
                    # если надо искать вопрос на определенную тематику - ищем
                    search = message.split(' ',1)
                    if len(search) > 1:
                        search = search[1]
                        search = search.strip('." ')
                        search = search.replace('"','')
                        search = search.lower()
                        search = search.replace('ё','е')
                        if search == '':
                            search = None
                    else:
                        search = None
                    # получаем вопрос, отправляем его сообщением
                    question, pic = getquestion(event,qtype,date,qset,search)
                    if question != None:
                        sendmessage(event,question,pic,getkeyboard(False))
                    # удаляем вопросы старше 1 дня (ибо лимит 10000 строк)
                    '''currtime = int(time.time())
                    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
                    cursor = conn.cursor()
                    values = (currtime,)
                    insert = 'DELETE FROM questions WHERE created < %s - 86400'
                    cursor.execute(insert,values)
                    conn.commit()
                    cursor.close()
                    conn.close()'''
                # пользователь просит ответ, помечаем вопрос как отвеченный и отправляем ответ и комментарий
                elif message == 'ответ':
                    qtype = getfromtab(event, 'qtype')
                    answer = getfromtab(event, 'answer')
                    # если вопрос свояка, то обрезаем ответ и просим следующий вопрос
                    if qtype == '5':
                        if answer != None:
                            answer = re.split('&&&', answer)
                            answer = answer[1].lower()
                            done = onsianswer(event,False,answer)
                    else:
                        comment = getfromtab(event, 'qcomments')
                        commentpic = getfromtab(event, 'commentpic')
                        tabid = event.obj.message['peer_id']
                        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
                        cursor = conn.cursor()
                        values = (tabid,)
                        insert = ('UPDATE questions SET answered = true WHERE tabid = %s')
                        cursor.execute(insert, values)
                        conn.commit()
                        cursor.close()
                        conn.close()
                        if answer != None:
                            sendmessage(event,answer,None,getkeyboard(True))
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
                        if source != None:
                            if '1. ' in source:
                                source = re.split('\d\. ',source)
                                while('' in source): 
                                    source.remove('') 
                                source = "\n".join(source)
                            sendmessage(event,source)
                # отправляем турнир
                elif message == 'турнир':
                    tour = getfromtab(event,'tour')
                    if tour != None:
                        sendmessage(event,tour)
                # если строка начинается с "о ", проверяем ответ (чтобы не читать весь спам из бесед, ибо лагать же будет)
                elif message.split(' ',1)[0] == 'о' and message.strip(' ') != 'о':
                    answered = getfromtab(event,'answered')
                    if answered == False:
                        answercheck(event) 
    except requests.exceptions.ReadTimeout as timeout:
        continue
