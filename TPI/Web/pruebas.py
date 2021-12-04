from flask import Flask, render_template, request, url_for, redirect, flash, session
import MySQLdb
from datetime import datetime, timedelta

import smtplib
from decouple import config

var1="juan"
var2="pablo"
var3="caperucita"
msj1='Hola '+var2+var1+'.\nLe comunicamos que ya tiene '
msj2='disponible para retirar en nuestra biblioteca el libro: '+var3
msj3='\nRecuerde que tiene un plazo de 3 (tres) días a partir de este mensaje '
msj4='para retirar el libro o cancelar su reserva.'
msj=msj1+msj2+msj3+msj4
message = 'Subject: {}\n\n{}'.format('Biblioteca Genérica te informa:', msj)
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login(config('EMAIL'), config('EMAIL_PASSWORD'))
server.sendmail('jorgenewells5555@gmail.com','newellselias3@gmail.com',message.encode('utf-8'))
server.quit()
print('mensaje enviado \n satisfactoriamente') 