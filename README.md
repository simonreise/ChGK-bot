# ChGK-bot
VK bot for db.chgk.info

ВК бот для Базы вопросов "Что? Где? Когда?

## Как пользоваться ботом
Основная группа с ботом:
https://vk.com/bot_chgk

Чтобы получить вопрос, просто напишите боту в личные сообщения.

Как добавить бота в беседу читайте в группе ВК: https://vk.com/@bot_chgk-kak-dobavit-bota-v-besedu

### Доступные команды
Капитализация текста не важна, то есть `вопрос`, `Вопрос` и `ВОПРОС` - это одна и та же команда

**Вопрос** - бот отправит вам вопрос

Дополнительные аргументы для команды "вопрос": 
* Тип вопроса - чгк/брейн/интернет-турнир/бескрылка/свояк/эрудит-футбол, по умолчанию - чгк
* Самая ранняя возможная дата вопроса в формате YYYY-MM-DD, например 2005-01-15, по умолчанию - 2010-01-01

Последовательность введения аргументов не важна

Примеры команд:

`вопрос` - получить вопрос чгк, написанный не ранее 1 января 2010

`вопрос свояк` - получить вопрос свояка, написанный не ранее 1 января 2010

`вопрос 1990-01-01` - получить вопрос чгк, написанный не ранее 1 января 1990

`вопрос эрудит-футбол 1992-02-13` - получить вопрос эрудит-футбола, написанный не ранее 13 февраля 1992

Если вы попросите у бота вопрос до того, как ответите на предыдущий, то бот отправит вам следующий вопрос и вернуться к предыдущему будет невозможно

Вопросы хранятся в базе данных одни сутки, потом удаляются. Это сделано потому что в базе данных Heroku есть ограничение 10 000 строк

**о [ваш ответ]** - отправить боту ваш ответ на вопрос

Если ответ верный, то бот ответит "Ответ правильный!"

Бот автоматически учитывает дополнительно указанные критерии ответа и информацию, указанную в ответе в [], убирает кавычки, пробелы и точки как в авторском ответе, так и в ответе пользователя

Например, на вопрос с ответом `[Профессор] [Филипп Филиппович] Преображенский` будут зачтены, например, ответы `о Преображенский`, `о Профессор Преображенский` и `о Филипп Филиппович Преображенский`, а на вопрос с ответом `"Phoenix".` и зачетом `"Феникс, Финикс"` будут зачтены ответы `о Phoenix`,`о Феникс` и `о Финикс`

**Ответ** - бот отправит вам ответ на вопрос и комментарий к вопросу

**Комментарий** - бот отправит вам комментарий к вопросу. Работает только если вы уже ответили на вопрос или попросили ответ

**Автор** - бот отправит вам информацию об авторе вопроса

**Источник** - бот отправит вам источники к вопросу. Работает только если вы уже ответили на вопрос или попросили ответ

**Турнир** - бот отправит вам название турнира, из которого взят вопрос

## Как запустить свою копию бота на хостинге Heroku

1. Зарегистрируйтесь и создайте новый проект
2. Подключите аддон heroku postgres
3. Любым удобным способом подключитесь к созданной базе данных и создайте таблицы `tokens` и `questions` по следующим шаблонам:

```
CREATE TABLE public.questions
(
    tabid bigint NOT NULL,
    question text COLLATE pg_catalog."default",
    pic text COLLATE pg_catalog."default",
    answer text COLLATE pg_catalog."default",
    pass text COLLATE pg_catalog."default",
    author text COLLATE pg_catalog."default",
    qcomments text COLLATE pg_catalog."default",
    commentpic text COLLATE pg_catalog."default",
    sources text COLLATE pg_catalog."default",
    tour text COLLATE pg_catalog."default",
    created integer NOT NULL,
    answered boolean NOT NULL,
    CONSTRAINT questions_pkey PRIMARY KEY (tabid)
)

TABLESPACE pg_default;
```

```
CREATE TABLE public.tokens
(
    name character varying COLLATE pg_catalog."default",
    token character varying COLLATE pg_catalog."default"
)
TABLESPACE pg_default;
```
4. Создайте группу ВК, сгенерируйте токен и загрузите его в таблицу `tokens`
5. Загрузите данные из этого репозитория на хостинг
6. Во вкладке resources запустите worker main.py
