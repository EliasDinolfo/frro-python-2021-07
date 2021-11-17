import MySQLdb
def funcion (contra, usuario):
    print(contra, usuario)
   
miConexion = MySQLdb.connect( host='localhost', user= 'root', passwd='nob159', db='biblioteca' )
cur = miConexion.cursor()
cur.execute( "SELECT contrasenia FROM usuario" )
for contra in cur.fetchall() :
    print (contra)
