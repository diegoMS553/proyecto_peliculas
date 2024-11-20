from flask import Flask, render_template, request, redirect, url_for
import database as db


app = Flask(__name__)


@app.route('/')
def movies_list():
    cursor = db.database.cursor(dictionary=True)
    cursor.execute("SELECT * FROM movies")
    movies = cursor.fetchall()
    cursor.close()
    return render_template('movies_list.html', movies=movies)

@app.route('/movies', methods=['GET'])
def movies_search_list():
    cursor = db.database.cursor(dictionary=True)
    search_query = request.args.get('search')

    if search_query:
        cursor.execute("SELECT * FROM movies WHERE title LIKE %s", ('%' + search_query + '%',))
    else:
        cursor.execute("SELECT * FROM movies")

    movies = cursor.fetchall()
    return render_template('movies_list.html', movies=movies)


@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    cursor = db.database.cursor(dictionary=True)
    cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()
    cursor.close()
    return render_template('movie_detail.html', movie=movie)

@app.route('/movie/create', methods=['GET', 'POST'])
def movie_create():
    if request.method == 'POST':
        title = request.form['title']
        director = request.form['director']
        genre = request.form['genre']
        year = request.form['year']
        synopsis = request.form['synopsis']
        image_url = request.form['image_url']  # Nuevo campo para la URL de la imagen

        cursor = db.database.cursor()
        cursor.execute(
            "INSERT INTO movies (title, director, genre, year, synopsis, image_url) VALUES (%s, %s, %s, %s, %s, %s)",
            (title, director, genre, year, synopsis, image_url)
        )
        db.database.commit()
        cursor.close()
        return redirect(url_for('movies_list'))
    
    return render_template('movie_create.html')


@app.route('/movie/edit/<int:movie_id>', methods=['GET', 'POST'])
def movie_edit(movie_id):
    cursor = db.database.cursor(dictionary=True)

    if request.method == 'POST':
        title = request.form['title']
        director = request.form['director']
        genre = request.form['genre']
        year = request.form['year']
        synopsis = request.form['synopsis']
        image_url = request.form['image_url']

        cursor.execute(
            "UPDATE movies SET title = %s, director = %s, genre = %s, year = %s, synopsis = %s, image_url = %s WHERE id = %s",

            (title, director, genre, year, synopsis, image_url, movie_id)
        )
        db.database.commit()
        cursor.close()
        return redirect(url_for('movies_list'))
    
    cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()
    cursor.close()
    
    return render_template('movie_edit.html', movie=movie)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/movie/delete/<int:movie_id>', methods=['POST'])
def movie_delete(movie_id):
    cursor = db.database.cursor()
    cursor.execute("DELETE FROM movies WHERE id = %s", (movie_id,))
    db.database.commit()
    cursor.close()
    return redirect(url_for('movies_list'))


if __name__ == '__main__':
    app.run(debug=True)
