from flask import Flask, render_template, request, url_for, redirect, flash, session
import MySQLdb
from datetime import datetime, timedelta
import smtplib
from decouple import config

app=Flask(__name__)

#para envio de emails se debe habilitar la opcion de navegador
#(solo el email que hará de remitente)
#https://myaccount.google.com/lesssecureapps

#mysql connection   
miConexion = MySQLdb.connect( host='localhost', user= 'root', passwd=config('DB_PASSWORD'), db='biblioteca' )

#settings
app.secret_key = 'mysecretkey'

#al cerrar el navegador, la sesión se cierra automaticamente o
#al borrar el historial de navegación
@app.before_request
def make_session_permanent():
    session.permanent = False
    #app.config['PERMANENT_SESSION_LIFETIME'] =  timedelta(minutes=1) #define el tiempo que se mantiene abierta la sesion

#funciones reutilizables
def obtenerFechaEstimada(isbn):
    #obtener fecha estimada de espera a través de los retiros
    cur = miConexion.cursor()
    cur.execute("""SELECT date_format(MIN(fecha_fin_prestamo), "%%d-%%m-%%Y"),
                titulo, imagen, CONCAT(nombre_autor,' ',apellido_autor)
                FROM retiro 
                INNER JOIN libro ON libro.isbn=retiro.isbn
                INNER JOIN libro_autor la ON la.isbn=libro.isbn
                INNER JOIN autor a ON a.id_autor=la.id_autor
                WHERE retiro.isbn=%s
                AND fecha_fin_prestamo>curdate()
                AND fecha_devolucion IS NULL""",(isbn,))
    data=cur.fetchone()
    if data and data[0]!=None:
        return data
    else:
        #obtener fecha estimada de espera a través de la reserva real que ya existe del libro
        cur.execute("""SELECT date_format(MIN(fecha_fin_reserva), "%%d-%%m-%%Y"),
                    titulo, imagen, CONCAT(nombre_autor,' ',apellido_autor)
                    FROM reserva 
                    INNER JOIN libro ON libro.isbn=reserva.isbn
                    INNER JOIN libro_autor la ON la.isbn=libro.isbn
                    INNER JOIN autor a ON a.id_autor=la.id_autor
                    WHERE reserva.isbn=%s
                    AND fecha_fin_reserva>curdate()
                    AND fecha_cancelacion IS NULL""",(isbn,))
        data=cur.fetchone()
        return data

#funcion para envio de email
def enviarMail(msj, destinatario):
    message = 'Subject: {}\n\n{}'.format('Biblioteca Genérica te informa:', msj)
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(config('EMAIL'), config('EMAIL_PASSWORD'))
    server.sendmail(config('EMAIL'), destinatario, message.encode('utf-8'))
    server.quit()

#página principal
@app.route('/')
def home():
    return render_template("home.html")

#inicio de sesión
@app.route('/signin')
def signin():
    #sanciones automaticas
    session.clear()
    return render_template("signin.html")

@app.route('/validarUsuario', methods=['POST'])
def validarUsuario():
    if request.method=='POST':
        usu=request.form['usuario']
        contra=request.form['contraseña']
        cur = miConexion.cursor()
        cur.execute("""SELECT u.id_usuario, u.nombre, u.apellido, u.tipo_usuario,
                    soc.nro_socio
                    FROM usuario u
		            LEFT JOIN socio soc on u.id_usuario=soc.id_usuario
		            WHERE nombre_usuario = %s
		            AND contrasenia = %s""", (usu,contra))
        row = cur.fetchone()
        if row and row[3]=='Socio':
            session['iduser'] = row[0]
            session['data'] = row[1]+' '+row[2]
            session['nrosocio']= row[4]
            return redirect(url_for('micuenta',id=session['iduser']))
        if row and row[0][3]=='Admin':
            flash("Aun no se ha hecho el caso de administradores, vuelva mas tarde")
            return render_template("signin.html")
        flash("Los datos ingresados son incorrectos")
        return render_template("signin.html")
    return render_template("signin.html")

#página principal de socio
@app.route('/<id>/micuenta', methods=['GET', 'POST'])
def micuenta(id):
    if 'iduser' in session and str(session['iduser'])==str(id):
        # cargar talleres
        cur=miConexion.cursor()
        cur.execute("""SELECT date_format(inicio_taller, "%%d-%%m-%%Y"),
                    fin_taller, nombre_taller, 
                    costo, dia_dictado, time_format(hora_inicio, "%%H:%%i"), 
                    time_format(hora_fin, "%%H:%%i"), duracion, forma_pago, 
                    date_format(fecha_inscripcion, "%%d-%%m-%%Y"), 
                    concat(nombre,' ',apellido), t.id_taller,
                    (CASE WHEN curdate()>inicio_taller THEN 'Si' ELSE 'No' END)'iniciado' 
                    FROM taller t 
                    INNER JOIN talleres_usuarios tu on t.id_taller=tu.id_taller
                    INNER JOIN disertante d on d.id_disertante=t.id_disertante
                    WHERE id_usuario=%s AND fin_taller>curdate()
                    AND tu.fecha_cancelacion is null""", (id,))
        data=cur.fetchall()
        # cargar reservas reales
        cur.execute("""SELECT date_format(res.fecha_inicio_reserva, "%%d-%%m-%%Y"),
                    res.isbn, res.nro_ejemplar,
                    date_format(res.fecha_fin_reserva, "%%d-%%m-%%Y"),
                    l.titulo, CONCAT(nombre_autor,' ',apellido_autor),
                    edi.razon_social, e.fecha_publicacion, e.estado_fisico, res.fecha_inicio_reserva
                    FROM reserva res
                    INNER JOIN libro l ON l.isbn=res.isbn
                    INNER JOIN ejemplar e ON e.isbn=l.isbn AND e.nro_ejemplar=res.nro_ejemplar
                    INNER JOIN editorial edi ON edi.id_editorial=e.id_editorial
                    INNER JOIN libro_autor la ON la.isbn=l.isbn
                    INNER JOIN autor a ON a.id_autor=la.id_autor
                    WHERE res.fecha_fin_reserva>curdate()
                    AND res.fecha_cancelacion IS NULL
                    AND res.nro_cola=0
                    AND res.nro_socio=%s""",(session['nrosocio'],))
        res=cur.fetchall()
        # cargar reservas en cola
        cur.execute("""SELECT date_format(res.fecha_inicio_reserva, "%%d-%%m-%%Y"),
                    res.isbn, l.titulo, 
                    CONCAT(nombre_autor,' ',apellido_autor),
					res.nro_cola, res.fecha_inicio_reserva
                    FROM reserva res
                    LEFT JOIN libro l ON l.isbn=res.isbn
                    LEFT JOIN libro_autor la ON la.isbn=l.isbn
                    LEFT JOIN autor a ON a.id_autor=la.id_autor
					WHERE res.fecha_cancelacion IS NULL
                    AND res.nro_cola <> 0
                    AND res.nro_socio=%s""",(session['nrosocio'],))
        res_cola=cur.fetchall()
        fechas_estimadas=[]
        if res_cola:
            for r in res_cola:
                fechas_estimadas.append(obtenerFechaEstimada(r[1]))
        # cargar sanciones
        cur.execute("""SELECT u.id_usuario, u.nombre, u.apellido, u.tipo_usuario, 
                    san.fecha_aplica_sancion, san.fecha_fin_sancion,
                    san.monto, san.descripcion, san.dias, san.fecha_abono, l.titulo
                    FROM usuario u
		            LEFT JOIN socio soc on u.id_usuario=soc.id_usuario
                    LEFT JOIN sancion san on soc.nro_socio=san.nro_socio
                    LEFT JOIN ejemplar e on e.nro_ejemplar=san.nro_ejemplar and e.isbn=san.isbn
                    LEFT JOIN libro l on l.isbn=e.isbn
		            WHERE u.id_usuario=%s""", (id,))
        rows = cur.fetchall()
        if len(rows)>0 and rows[0][3]=='Socio':
            cur.execute("""UPDATE socio
                        SET estado_socio='Activo'
                        WHERE id_usuario=%s""", (id,))
            session['estadosocio'] = 'Activo'
            lista_sanciones_monetarias = []
            lista_sanciones_de_dias = []
            for row in rows:
                #sancion monetaria
                if row[6]!=None and row[9]==None:
                    session['estadosocio'] = 'Sancionado'
                    cur.execute("""UPDATE socio
                        SET estado_socio='Sancionado'
                        WHERE id_usuario=%s""", (id,))
                    miConexion.commit()
                    fecha_inicio = row[4].strftime("%d-%m-%Y")
                    fecha_fin = row[5].strftime("%d-%m-%Y")
                    lista_sanciones_monetarias.append([fecha_inicio, fecha_fin, row[6], row[7], row[10]])
                #sancion de dias
                elif row[8]!=None and row[5]>datetime.now():
                    session['estadosocio'] = 'Sancionado'
                    cur.execute("""UPDATE socio
                        SET estado_socio='Sancionado'
                        WHERE id_usuario=%s""", (id,))
                    miConexion.commit()
                    fecha_inicio = row[4].strftime("%d-%m-%Y")
                    fecha_fin = row[5].strftime("%d-%m-%Y")
                    lista_sanciones_de_dias.append([fecha_inicio,fecha_fin, row[7], row[8], row[10]])
        return render_template("micuenta.html", talleres=data, sancionesM=lista_sanciones_monetarias,
        sancionesD=lista_sanciones_de_dias, reservas=res, reservas_cola=res_cola, fechas=fechas_estimadas)
    return redirect(url_for('signin'))

#talleres
@app.route('/talleres')
def talleres():
    cur = miConexion.cursor()
    cur.execute("""SELECT id_taller, date_format(inicio_taller, "%d-%m-%Y"), 
                fin_taller, nombre_taller, cupo, costo, dia_dictado, 
                time_format(hora_inicio, "%H:%i"), 
                time_format(hora_fin, "%H:%i"), imagen, duracion,
                CONCAT(nombre,' ',apellido) 
                FROM taller t INNER JOIN disertante d
                ON t.id_disertante=d.id_disertante  
                WHERE inicio_taller>current_date()""")   
    data = cur.fetchall()
    cur.close()
    return render_template("talleres.html", talleres=data)

@app.route('/pagarTaller')
def pagarTaller():
    if 'iduser' in session:
        idtaller=request.args.get('idtaller')
        costo=request.args.get('costo')
        cur = miConexion.cursor()
        cur.execute("""SELECT * FROM talleres_usuarios tu
                    INNER JOIN taller t ON t.id_taller=tu.id_taller
                    WHERE tu.id_taller=%s AND tu.id_usuario=%s
                    AND tu.fecha_cancelacion is null""", (idtaller,session['iduser']))
        row=cur.fetchone()
        if row:
            flash('Usted ya está inscripto en el curso.')
            flash('Método de pago efectuado: '+row[3])
            cur.close()
            return redirect(url_for('talleres'))
        if int(costo)==0:
            #crear registro de inscripcion al taller gratuito
            cur.execute("""INSERT INTO talleres_usuarios 
                        (id_taller, id_usuario, fecha_inscripcion, forma_pago)
                        VALUES (%s, %s, current_timestamp(), 'Taller Gratuito' )""", (idtaller, session['iduser']))
            miConexion.commit()
            #disminuir cupo en 1 
            cur.execute("""UPDATE taller
                        SET cupo=cupo-1
                       WHERE id_taller=%s""", (idtaller,))
            miConexion.commit()
            flash('Usted se ha inscripto a un taller gratuito.')
            return redirect(url_for('talleres'))
        return render_template("pagarTaller.html")
    flash("Debe iniciar sesión para inscribirse en talleres.")
    return render_template("signin.html")

@app.route('/confirmarPagoTaller', methods=['POST'])
def confirmarPagoTaller():
    #crear registro de inscripcion al taller de pago
    idtaller=request.args.get('idtaller')
    metodo=request.args.get('metodo')
    cur = miConexion.cursor()
    cur.execute("""INSERT INTO talleres_usuarios
                        (id_taller, id_usuario, fecha_inscripcion, forma_pago)
                        VALUES (%s, %s, current_timestamp(), %s)""", (idtaller, session['iduser'], metodo))
    miConexion.commit()
    #disminuir cupo en 1 
    cur.execute("""UPDATE taller
                SET cupo=cupo-1
                WHERE id_taller=%s""", (idtaller,))
    miConexion.commit()
    flash('Usted se ha inscripto al taller.')
    return redirect(url_for('talleres', id=session['iduser']))

@app.route('/eliminarInscripcion')
def eliminarInscripcion():
    #eliminar inscripcion al taller
    idtaller=request.args.get('idtaller')
    cur = miConexion.cursor()
    cur.execute("""UPDATE talleres_usuarios
                SET fecha_cancelacion=current_timestamp()
                WHERE id_taller=%s AND id_usuario=%s
                AND fecha_cancelacion is null""", (idtaller, session['iduser']))
    miConexion.commit()
    #aumentar cupo en 1
    cur.execute("""UPDATE taller
                SET cupo=cupo+1
                WHERE id_taller=%s""", (idtaller,))
    miConexion.commit()
    flash("""Usted canceló su inscripción. Recuerde que si el taller no era gratuito
    y no lo abonó a través de tarjeta de crédito/débito, puede solicitar el reembolso
    en la biblioteca""")
    return redirect(url_for('micuenta', id=session['iduser']))

#catalogo de libros
@app.route('/catalogo')
def catalogo():
    #cargar catalogo de libros
    cur = miConexion.cursor()
    cur.execute("""SELECT libro.isbn, titulo, nombre_autor, 
                apellido_autor, imagen,
		        COUNT(e.isbn) 'Cantidad de ejemplares', 
                COUNT(CASE WHEN e.estado_vigencia = 'Inactivo' THEN 1 END) 'Inactivos',
                sinopsis
				FROM libro
                INNER JOIN libro_autor on libro.isbn=libro_autor.isbn
                INNER JOIN autor on autor.id_autor=libro_autor.id_autor
				LEFT JOIN ejemplar e on e.isbn=libro.isbn
                GROUP BY libro.isbn
                ORDER BY titulo""")
    data = cur.fetchall()
    cur.close()
    return render_template("catalogo.html", libros=data)

@app.route('/filtrarcatalogo', methods=['POST'])
def filtrarcatalogo():
        tit=request.form['libro']
        fil=request.form['filtro'] #'radio1' o 'radio2'
        mod=request.form['modo'] #'1' o '2'
        cur = miConexion.cursor()
        if request.form['filtro']=="radio1":
            cur.execute("""SELECT libro.isbn, titulo, nombre_autor, 
                        apellido_autor, imagen,
		                COUNT(e.isbn) 'Cantidad de ejemplares', 
                        COUNT(CASE WHEN e.estado_vigencia = 'Inactivo' THEN 1 END) 'Inactivos',
                        sinopsis
				        FROM libro
                        INNER JOIN libro_autor on libro.isbn=libro_autor.isbn
                        INNER JOIN autor on autor.id_autor=libro_autor.id_autor
				        LEFT JOIN ejemplar e on e.isbn=libro.isbn
                        WHERE titulo like %s
                        GROUP BY libro.isbn
                        ORDER BY titulo""", ('%'+tit+'%',))
        else:
            cur.execute("""SELECT libro.isbn, titulo, nombre_autor, 
                        apellido_autor, imagen,
		                COUNT(e.isbn) 'Cantidad de ejemplares', 
                        COUNT(CASE WHEN e.estado_vigencia = 'Inactivo' THEN 1 END) 'Inactivos',
                        sinopsis
				        FROM libro
                        INNER JOIN libro_autor on libro.isbn=libro_autor.isbn
                        INNER JOIN autor on autor.id_autor=libro_autor.id_autor
				        LEFT JOIN ejemplar e on e.isbn=libro.isbn
                        WHERE CONCAT(nombre_autor,' ',apellido_autor) like %s
                        GROUP BY libro.isbn
                        ORDER BY titulo""", ('%'+tit+'%',))
        data = cur.fetchall()
        cur.close()
        return render_template("catalogo.html", libros=data, filtro=fil, modo=mod)

#reservar libros
@app.route('/reservar', methods=['GET','POST'])
def reservar():
    if 'iduser'in session:
        isbn=request.args.get('isbn')
        cur = miConexion.cursor()
        #compruebo que el mismo socio no tenga ya una reserva sin finalizar o un 
        #retiro sin devolución del mismo libro o ya encontrarse en cola
        cur.execute("""SELECT * FROM reserva
                    WHERE isbn=%s AND nro_socio=%s 
                    AND fecha_cancelacion IS NULL 
                    AND (curdate()<fecha_fin_reserva
                    OR fecha_fin_reserva IS NULL)""", (isbn,session['nrosocio'],))
        reserva=cur.fetchone()
        cur.execute("""SELECT * FROM retiro
                    WHERE isbn=%s AND nro_socio=%s
                    AND fecha_devolucion IS NULL""",(isbn,session['nrosocio'],))
        retiro=cur.fetchone()
        if reserva:
            flash('Ya tiene una reserva realizada del libro seleccionado.')
            return redirect(url_for('catalogo'))
        if retiro:
            flash('Ya tiene un retiro sin devolución del libro seleccionado.')
            return redirect(url_for('catalogo'))
        # compruebo que el mismo socio no tenga 5 reservas reales sin finalizar
        cur.execute("""SELECT * FROM reserva
                    WHERE nro_socio=%s 
                    AND fecha_cancelacion IS NULL 
                    AND curdate()<fecha_fin_reserva""", (session['nrosocio'],))
        reservas_reales=cur.fetchall()
        if reservas_reales and len(reservas_reales)>4:
            flash('Ya excedió el limite de reservas activas permitidas (hasta 5).')
            return redirect(url_for('catalogo'))
        # caso 1 al menos un ejemplar disponible
        # obtengo uno de los ejemplares disponibles (el de mejor estado físico)
        cur.execute("""SELECT e.isbn, l.titulo, 
                e.estado_fisico, e.fecha_publicacion, e.nro_edicion, 
                edi.razon_social, l.imagen, concat(a.nombre_autor,' ',apellido_autor),
                e.nro_ejemplar
                FROM ejemplar e
                INNER JOIN libro l ON l.isbn=e.isbn
                INNER JOIN editorial edi ON e.id_editorial=edi.id_editorial
                INNER JOIN libro_autor la ON la.isbn=l.isbn
                INNER JOIN autor a ON la.id_autor=a.id_autor
                WHERE e.isbn=%s AND estado_reserva='Disponible'
                ORDER BY estado_fisico
                LIMIT 1""", (isbn,))
        data = cur.fetchone()
        if data:
            return render_template('reservar.html', ejemplar=data, isbn=isbn)
        #caso 2 no hay ejemplares disponibles (cola de reserva)
        else:
            #obtener proximo numero de cola
            cur.execute("""SELECT MAX(nro_cola) FROM reserva
                        WHERE isbn=%s""", (isbn,))
            row=cur.fetchone()
            if row and row[0]!=0:
                nro_cola_prox=row[0]+1
            else:
                nro_cola_prox=1
            #obtener fecha estimada de espera a través de los retiros
            data=obtenerFechaEstimada(isbn)
            print(data)
            return render_template('reservar.html', nro_cola=nro_cola_prox,
            libro_fecha=data, isbn=isbn)
    flash("Debe iniciar sesión para poder reservar libros.")
    return render_template("signin.html")

#crear reserva
@app.route('/crearReserva')
def crearReserva():
    if 'iduser'in session:
        isbn=request.args.get('_isbn')
        nro_ejemplar=request.args.get('nro_ejemplar')
        cur = miConexion.cursor()
        #creacion registro de reserva
        cur.execute("""INSERT INTO reserva (fecha_inicio_reserva, isbn, 
        nro_socio, nro_ejemplar, fecha_fin_reserva, nro_cola)
        VALUES (current_timestamp(), %s, %s, %s, DATE_ADD(curdate(), INTERVAL 3 DAY), 0)""",
        (isbn, session['nrosocio'], nro_ejemplar,))
        miConexion.commit()
        #obtener la fecha de fin de reserva luego de insertar el registro
        cur.execute("SELECT DATE_FORMAT(DATE_ADD(curdate(), INTERVAL 3 DAY), '%d-%m-%Y')")
        fecha_fin_reserva=cur.fetchone()
        #actualizacion del estado del ejemplar
        cur.execute("""UPDATE ejemplar
                    SET estado_reserva='Reservado'
                    WHERE nro_ejemplar=%s AND isbn=%s""",(nro_ejemplar,isbn))
        miConexion.commit()
        cur.close()
        flash('Libro reservado. Tiene fecha de retiro hasta el: '+str(fecha_fin_reserva[0])+ ", inclusive")
        return redirect(url_for('catalogo'))
    return render_template('signin.html')

# crear cola de reserva
@app.route("/crearColaReserva")
def crearColaReserva():
    if 'iduser' in session:
            isbn=request.args.get('_isbn')
            nro_cola=request.args.get('_nro_cola')
            cur = miConexion.cursor()
            #creacion registro de reserva
            cur.execute("""INSERT INTO reserva (fecha_inicio_reserva, isbn, 
                        nro_socio, nro_cola)
                        VALUES (current_timestamp(), %s, %s, %s)""",
                        (isbn, session['nrosocio'], nro_cola,))
            miConexion.commit()
            flash("""¡Entró en la cola de espera del libro! 
            Recuerde que el día que haya un ejemplar disponible, le será notificado por email y por el mismo sitio
            y tendrá un plazo de 3 días para retirar el libro o cancelar su reserva.""")
            return redirect(url_for('catalogo'))
    return render_template("signin.html")

#cancelar reserva
@app.route("/cancelarReserva")
def cancelarReserva():
    if 'iduser' in session:
        isbn=request.args.get('isbn')
        fecha_inicio=request.args.get('fecha_inicio')
        nro_ejemplar=request.args.get('nro_ejemplar')
        # registrar la fecha de cancelacion de reserva
        cur = miConexion.cursor()
        cur.execute("""UPDATE reserva
                    SET fecha_cancelacion=curdate()
                    WHERE fecha_inicio_reserva=%s
                    AND nro_ejemplar=%s
                    AND isbn=%s
                    AND fecha_cancelacion IS NULL""", (fecha_inicio,nro_ejemplar,isbn,))
        miConexion.commit()
        # actualizar estado del ejemplar a disponible
        cur.execute("""UPDATE ejemplar
                    SET estado_reserva='Disponible'
                    WHERE nro_ejemplar=%s
                    AND isbn=%s""",(nro_ejemplar, isbn,))
        miConexion.commit()
        # verificar y actualizar nro_cola si hay socios en cola de espera por ese libro
        cant_filas_afectadas=cur.execute("""UPDATE reserva
                    SET fecha_inicio_reserva = CASE WHEN nro_cola=1 THEN current_timestamp() ELSE fecha_inicio_reserva END,
                    fecha_fin_reserva = CASE WHEN nro_cola=1 THEN DATE_ADD(curdate(), INTERVAL 3 DAY) ELSE NULL END,
                    nro_ejemplar = CASE WHEN nro_cola=1 THEN %s ELSE NULL END,
                    nro_cola=nro_cola-1
                    WHERE isbn=%s AND nro_cola <> 0""", (nro_ejemplar, isbn,))
        miConexion.commit()
        if cant_filas_afectadas>0:
            cur.execute("""SELECT res.fecha_inicio_reserva, res.fecha_fin_reserva,
                        email ,nombre, apellido, titulo
                        FROM reserva res
                        INNER JOIN socio soc ON res.nro_socio=soc.nro_socio
                        INNER JOIN usuario usu ON soc.id_usuario=usu.id_usuario
                        INNER JOIN ejemplar e ON e.isbn=res.isbn AND res.nro_ejemplar=e.nro_ejemplar
                        INNER JOIN libro l ON l.isbn=res.isbn
                        WHERE res.nro_ejemplar=%s
                        AND res.isbn=%s
                        AND res.fecha_cancelacion IS NULL 
                        AND res.fecha_retiro IS NULL
                        AND fecha_fin_reserva>curdate()
                        AND res.nro_cola=0""", (nro_ejemplar, isbn,))
            row=cur.fetchone()
            #volver a colocar el ejemplar como reservado
            cur.execute("""UPDATE ejemplar
                    SET estado_reserva='Reservado'
                    WHERE nro_ejemplar=%s
                    AND isbn=%s""",(nro_ejemplar, isbn,))
            miConexion.commit()
            #envio de email notificando de la creacion de reserva para el socio
            #que se encontraba nro 1 en cola
            msj1='Hola '+row[3]+' '+row[4]+'.\nLe comunicamos que ya tiene '
            msj2='disponible para retirar en nuestra biblioteca el libro: '+row[5]
            msj3='\nRecuerde que tiene un plazo de 3 (tres) días a partir de este mensaje '
            msj4='para retirar el libro o cancelar su reserva.'
            msj=msj1+msj2+msj3+msj4
            enviarMail(msj, row[2])
        flash("Cancelaste la reserva del libro.")
        return redirect(url_for('micuenta', id=session['iduser']))
    return render_template("signin.html")

# cancelar cola de reserva
@app.route('/cancelarColaReserva')
def cancelarColaReserva():
    if 'iduser' in session:
        isbn=request.args.get('isbn')
        fecha_inicio=request.args.get('fecha_inicio')
        nro_cola=request.args.get('nro_cola')
        # registrar la fecha de cancelacion de reserva y el nro de cola en 0
        cur = miConexion.cursor()
        cur.execute("""UPDATE reserva
                    SET fecha_cancelacion=curdate(),
                    nro_cola=0
                    WHERE fecha_inicio_reserva=%s
                    AND isbn=%s
                    AND fecha_cancelacion IS NULL""", (fecha_inicio,isbn,))
        miConexion.commit()
        # verificar y actualizar nro_cola el resto de nro de colas superiores para ese libro
        cur.execute("""UPDATE reserva
                    SET nro_cola=nro_cola-1
                    WHERE isbn=%s AND nro_cola > %s""", (isbn, nro_cola,))
        miConexion.commit()
        flash("Cancelaste la cola de espera del libro.")
        return redirect(url_for('micuenta', id=session['iduser']))
    return render_template("signin.html")

# página de Más Info
@app.route('/masInfo')
def masInfo():
    return render_template("masInfo.html")

# programa principal
if __name__ == '__main__': 
    app.run(port=3000, debug=True)

#Ejecución en terminal:


#en caso de cancelar cola de reserva, eliminar registro fisico de la base de datos
#pie de pagina con biblioteca generica, localidad, provincia, pais, direccion, contacto: email, telefono


#python practica-2021/TPI/Web/app.py