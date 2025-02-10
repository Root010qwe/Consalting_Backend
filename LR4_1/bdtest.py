import psycopg2

conn = psycopg2.connect(dbname="postgres", host="192.168.0.189", user="student", password="root", port="5432")

cursor = conn.cursor()
 
cursor.execute("INSERT INTO public.books (id, name, description) VALUES(1, 'Мастер и Маргарита', 'Крутая книга')")
 
conn.commit()   
 
cursor.close()
conn.close()