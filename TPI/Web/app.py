from flask import Flask, render_template, request, url_for, redirect, flash
import MySQLdb

app=Flask(__name__)

#mysql connection   
miConexion = MySQLdb.connect( host='localhost', user= 'root', passwd='nob159', db='biblioteca' )

#settings
app.secret_key = 'mysecretkey'


@app.route('/')
def Index():
    return render_template("login.html")

@app.route('/inicio_sesion', methods=['POST'])
def inicio_sesion():
    if request.method=='POST':
        usu=request.form['usuario']
        contra=request.form['contra']
        cur = miConexion.cursor()
        cur.execute("SELECT * FROM usuario WHERE nombre_usuario = %s AND contrasenia = %s", (usu,contra))
        row = cur.fetchone()
        if row:
            return redirect(url_for('home', id=row[0]))
        flash("Usuario o contraseña incorrecta")
        return redirect(url_for('Index'))

@app.route('/<id>/home', methods=['GET', 'POST'])
def home(id):
    cur = miConexion.cursor()
    cur.execute("SELECT nombre, apellido FROM usuario WHERE id_usuario = %s",(id))
    row = cur.fetchone()
    flash(row[0]+" "+row[1])
    return render_template("home.html")

if __name__ == '__main__': 
    app.run(port=3000, debug=True)