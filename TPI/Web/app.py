from flask import Flask, render_template, request, url_for, redirect, flash, session
import MySQLdb

app=Flask(__name__)

#mysql connection   
miConexion = MySQLdb.connect( host='localhost', user= 'root', passwd='nob159', db='biblioteca' )

#settings
app.secret_key = 'mysecretkey'


@app.route('/')
def home():
    return render_template("home.html")

@app.route('/signin')
def signin():
    session.pop('iduser', None)
    session.pop('data', None)
    return render_template("signin.html")

@app.route('/validarUsuario', methods=['POST'])
def validarUsuario():
    if request.method=='POST':
        usu=request.form['usuario']
        contra=request.form['contraseña']
        cur = miConexion.cursor()
        cur.execute("""SELECT * FROM usuario WHERE nombre_usuario = %s 
                    AND contrasenia = %s""", (usu,contra))
        row = cur.fetchone()
        if row:
            session['iduser'] = row[0]
            session['data'] = row[4]+' '+row[5]
            return redirect(url_for('micuenta', id=row[0]))
        flash("Los datos ingresados son incorrectos")
        return render_template("signin.html")
    return render_template("signin.html")

@app.route('/<id>/micuenta', methods=['GET', 'POST'])
def micuenta(id):
    return render_template("micuenta.html")

@app.route('/talleres')
def talleres():
    cur = miConexion.cursor()
    cur.execute("""SELECT id_taller, date_format(inicio_taller, "%d-%m-%Y"), 
                fin_taller, nombre_taller, cupo, costo, dia_dictado, 
                time_format(hora_inicio, "%H:%i"), 
                time_format(hora_fin, "%H:%i"), imagen, duracion 
                FROM taller 
                WHERE inicio_taller>current_date()""")
    data = cur.fetchall()
    cur.close()
    return render_template("talleres.html", talleres=data)

@app.route('/pagarTaller')
def pagarTaller():
    if 'iduser' in session:
        idtaller=request.args.get('idtaller')
        cur = miConexion.cursor()
        cur.execute("""SELECT * FROM talleres_usuarios tu
                    INNER JOIN taller t ON t.id_taller=tu.id_taller
                    WHERE tu.id_taller=%s AND tu.id_usuario=%s""", (idtaller,session['iduser']))
        row=cur.fetchone()
        if row:
            flash('Usted ya está inscripto en el curso.')
            flash('Método de pago efectuado: '+row[2])
            cur.close()
            return redirect(url_for('talleres'))
        cur.execute("""SELECT id_taller, costo FROM taller
                    WHERE id_taller=%s""", (idtaller))
        row=cur.fetchone()
        if row[1]==0:
            cur.execute("""INSERT INTO talleres_usuarios 
                        (id_taller, id_usuario, forma_pago)
                        VALUES (%s, %s, 'Taller Gratuito')""", (idtaller, session['iduser']))

            flash('Usted se ha inscripto al taller.')
            return redirect(url_for('talleres'))
        return render_template("pagarTaller.html")
    flash("Debe iniciar sesión para inscribirse en talleres.")
    return render_template("signin.html")

@app.route('/catalogo')
def catalogo():
    cur = miConexion.cursor()
    cur.execute("""SELECT libro.isbn, titulo, nombre_autor, apellido_autor from libro
                inner join libro_autor on libro.isbn=libro_autor.isbn
                inner join autor on autor.id_autor=libro_autor.id_autor
                order by titulo""")
    data = cur.fetchall()
    cur.close()
    return render_template("catalogo.html", libros=data)

@app.route('/filtrarcatalogo', methods=['POST'])
def filtrarcatalogo():
        tit=request.form['libro']
        cur = miConexion.cursor()
        if request.form['filtro']=="radio1":
            cur.execute("""SELECT isbn, titulo, nombre_autor, apellido_autor from libro
                inner join libro_autor on libro.isbn=libro_autor.isbn
                inner join autor on autor.id_autor=libro_autor.id_autor
                where titulo like %s""", ('%'+tit+'%',))
        else:
            cur.execute("""SELECT isbn, titulo, nombre_autor, apellido_autor from libro
                inner join libro_autor on libro.isbn=libro_autor.isbn
                inner join autor on autor.id_autor=libro_autor.id_autor
                where concat(nombre_autor,' ',apellido_autor) like %s""", ('%'+tit+'%',))
        data = cur.fetchall()
        cur.close()
        return render_template("catalogo.html", libros=data)

@app.route('/reservar', methods=['GET','POST'])
def reservar():
    if 'iduser'in session:
        #isbn=request.args.get('isbn')


        return render_template("reservar.html")
    flash("Debe iniciar sesión para poder reservar libros.")
    return render_template("signin.html")

@app.route('/historia')
def historia():
    return render_template("historia.html")

if __name__ == '__main__': 
    app.run(port=3000, debug=True)

#Ejecución en terminal:
#python practica-2021/TPI/Web/app.py