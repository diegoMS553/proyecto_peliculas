from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_bcrypt import Bcrypt
from rating import get_movie_rating
import database as db
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'
bcrypt = Bcrypt(app)

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


@app.route('/movie/<int:movie_id>', methods=['GET', 'POST'])
def movie_detail(movie_id):
    # Obtener la película
    cursor = db.database.cursor(dictionary=True)
    cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()
    
    # Si la película no existe
    if not movie:
        cursor.close()
        return "Película no encontrada", 404

    # Obtener el promedio y total de ratings
    average_rating, total_ratings = get_movie_rating(movie_id)
    
    # Obtener listas personalizadas del usuario
    custom_lists = []
    if session.get('user_id'):
        cursor.execute("""
            SELECT id, name
            FROM custom_lists
            WHERE user_id = %s
        """, (session['user_id'],))
        custom_lists = cursor.fetchall()



    # Verificar si el usuario ya votó
    user_already_rated = False
    if session.get('user_id'):
        cursor.execute("""
            SELECT id FROM ratings WHERE movie_id = %s AND user_id = %s
        """, (movie_id, session['user_id']))
        user_already_rated = cursor.fetchone() is not None

    # Paginación de comentarios
    page = request.args.get('page', default=1, type=int)
    items_per_page = 5  # Número de comentarios por página
    offset = (page - 1) * items_per_page

    # Obtener los comentarios paginados
    cursor.execute("""
        SELECT c.id, c.comment, c.created_at, u.username, c.user_id
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.movie_id = %s
        ORDER BY c.created_at DESC
        LIMIT %s OFFSET %s
    """, (movie_id, items_per_page, offset))
    comments = cursor.fetchall()

    # Calcular el número total de comentarios y páginas
    cursor.execute("SELECT COUNT(*) AS total FROM comments WHERE movie_id = %s", (movie_id,))
    total_comments = cursor.fetchone()['total']
    total_pages = (total_comments + items_per_page - 1) // items_per_page

    # Manejar el envío de comentarios o calificaciones
    if request.method == 'POST' and not user_already_rated:
        if 'comment' in request.form and session.get('user_id'):
            # Guardar comentario
            comment_text = request.form['comment']
            user_id = session['user_id']
            cursor.execute("""
                INSERT INTO comments (movie_id, user_id, comment)
                VALUES (%s, %s, %s)
            """, (movie_id, user_id, comment_text))
            db.database.commit()
            flash("Comentario agregado exitosamente", "success")
            return redirect(url_for('movie_detail', movie_id=movie_id))

        elif 'rating' in request.form and session.get('user_id'):
            # Guardar rating si no ha votado
            rating = int(request.form['rating'])
            cursor.execute("""
                INSERT INTO ratings (movie_id, user_id, rating)
                VALUES (%s, %s, %s)
            """, (movie_id, session['user_id'], rating))
            db.database.commit()
            flash("¡Gracias por calificar esta película!", "success")
            return redirect(url_for('movie_detail', movie_id=movie_id))

    cursor.close()
    print(custom_lists)  # Depurar listas obtenidas

    return render_template(
        'movie_detail.html',
        movie=movie,
        average_rating=average_rating,
        total_ratings=total_ratings,
        comments=comments,
        total_pages=total_pages,
        page=page,
        user_already_rated=user_already_rated,
        custom_lists=custom_lists  # Pasar las listas personalizadas
)


@app.route('/movie/<int:movie_id>/comments')
def movie_comments(movie_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    cursor = db.database.cursor(dictionary=True)

    # Obtener los comentarios
    cursor.execute("""
        SELECT c.comment, c.created_at, u.username 
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.movie_id = %s
        ORDER BY c.created_at DESC
    """, (movie_id,))
    comments = cursor.fetchall()

    # Obtener detalles de la película
    cursor.execute("SELECT id, title FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()
    cursor.close()

    return render_template('movie_comments.html', movie=movie, comments=comments)



@app.route('/movie/<int:movie_id>/comment', methods=['POST'])
def add_comment(movie_id):
    # Verificar si el usuario está logueado
    if not session.get('user_id'):
        flash("Debes iniciar sesión para comentar", "warning")
        return redirect(url_for('login'))

    # Obtener el texto del comentario del formulario
    comment_text = request.form['comment']
    user_id = session['user_id']

    # Insertar el comentario en la base de datos
    cursor = db.database.cursor()
    cursor.execute("""
        INSERT INTO comments (movie_id, user_id, comment)
        VALUES (%s, %s, %s)
    """, (movie_id, user_id, comment_text))
    db.database.commit()

    flash("Comentario agregado exitosamente", "success")
    return redirect(url_for('movie_detail', movie_id=movie_id))

@app.route('/movie/<int:movie_id>/comment/edit/<int:comment_id>', methods=['GET', 'POST'])
def edit_comment(movie_id, comment_id):
    # Verificar si el usuario está logueado
    if not session.get('user_id'):
        flash("Debes iniciar sesión para editar un comentario", "warning")
        return redirect(url_for('login'))

    # Obtener el comentario de la base de datos
    cursor = db.database.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM comments WHERE id = %s AND user_id = %s
    """, (comment_id, session['user_id']))
    comment = cursor.fetchone()

    # Si no se encuentra el comentario o el usuario no es el propietario, redirigir
    if not comment:
        flash("Comentario no encontrado o no tienes permiso para editarlo", "danger")
        return redirect(url_for('movie_detail', movie_id=movie_id))

    if request.method == 'POST':
        new_comment = request.form['comment']

        # Actualizar el comentario en la base de datos
        cursor.execute("""
            UPDATE comments SET comment = %s WHERE id = %s
        """, (new_comment, comment_id))
        db.database.commit()

        flash("Comentario actualizado exitosamente", "success")
        return redirect(url_for('movie_detail', movie_id=movie_id))

    return render_template('edit_comment.html', movie_id=movie_id, comment=comment)


@app.route('/movie/create', methods=['GET', 'POST'])
def movie_create():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
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


@app.route('/admin/edit_movie/<int:movie_id>', methods=['GET', 'POST'])
def edit_movie(movie_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))

    cursor = db.database.cursor(dictionary=True)
    cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()

    if not movie:
        flash('Película no encontrada.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        director = request.form['director']
        genre = request.form['genre']
        year = request.form['year']
        synopsis = request.form['synopsis']
        image_url = request.form['image_url']

        cursor.execute("""
            UPDATE movies
            SET title = %s, director = %s, genre = %s, year = %s, synopsis = %s, image_url = %s
            WHERE id = %s
        """, (title, director, genre, year, synopsis, image_url, movie_id))
        db.database.commit()
        flash('Película actualizada exitosamente.', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('movie_edit.html', movie=movie)



@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/movie/delete/<int:movie_id>', methods=['POST'])
def movie_delete(movie_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    try:
        cursor = db.database.cursor()
        cursor.execute("DELETE FROM movies WHERE id = %s", (movie_id,))
        db.database.commit()
        cursor.close()
        flash(f"Película con ID {movie_id} eliminada exitosamente.", "success")
        print(f"Movie with ID {movie_id} deleted successfully.")
    except Exception as e:
        flash("Hubo un error al intentar eliminar la película.", "danger")
        print(f"Error deleting movie: {e}")
    
    # Verifica de dónde se originó la solicitud para redirigir adecuadamente
    next_page = request.form.get('next', 'movies_list')
    return redirect(url_for(next_page))


@app.route('/admin/delete_movie/<int:movie_id>', methods=['POST'])
def delete_movie(movie_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))

    cursor = db.database.cursor()
    cursor.execute("DELETE FROM movies WHERE id = %s", (movie_id,))
    db.database.commit()
    flash('Película eliminada exitosamente.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/movie/search', methods=['GET', 'POST'])
def movie_search():
    movies = []
    if request.method == 'POST':
        search_query = request.form['query']
        cursor = db.database.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM movies WHERE title LIKE %s OR genre LIKE %s OR director LIKE %s",
            (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%")
        )
        movies = cursor.fetchall()
        cursor.close()
    return render_template('movie_search.html', movies=movies)

# Ruta para registro
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        cursor = db.database.cursor(dictionary=True)  # Usar db.database
        cursor.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)', (username, password, 'user'))  # Rol por defecto: 'user'
        db.database.commit()
        cursor.close()

        flash('Usuario registrado exitosamente. Inicia sesión.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

#Agregar un admin
@app.route('/admin/add', methods=['GET', 'POST'])
def add_admin():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        cursor = db.database.cursor(dictionary=True)
        cursor.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)', 
                    (username, password, 'admin'))
        db.database.commit()
        cursor.close()

        flash('Administrador agregado exitosamente.', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_admin.html')


# Ruta para login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = db.database.cursor(dictionary=True)  # Usar db.database
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        cursor.close()

        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))

        flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')


# Ruta para el dashboard de usuarios
@app.route('/user/dashboard', methods=['GET', 'POST'])
def user_dashboard():
    if 'user_id' not in session:
        flash('Por favor inicia sesión para acceder a tu dashboard.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    cursor = db.database.cursor(dictionary=True)

    # Obtener películas favoritas
    cursor.execute("""
        SELECT m.id, m.title, m.image_url
        FROM movies m
        JOIN favorites f ON m.id = f.movie_id
        WHERE f.user_id = %s
    """, (user_id,))
    favorites = cursor.fetchall()

    # Obtener listas personalizadas
    cursor.execute("""
        SELECT id, name, created_at
        FROM custom_lists
        WHERE user_id = %s
    """, (user_id,))
    custom_lists = cursor.fetchall()

    # Obtener los elementos de cada lista personalizada
    lists_with_movies = []
    for custom_list in custom_lists:
        cursor.execute("""
            SELECT m.id, m.title, m.image_url
            FROM custom_list_items cli
            JOIN movies m ON cli.movie_id = m.id
            WHERE cli.list_id = %s
        """, (custom_list['id'],))
        movies_in_list = cursor.fetchall()
        custom_list['movies'] = movies_in_list
        lists_with_movies.append(custom_list)

    cursor.close()
    return render_template('user_dashboard.html', favorites=favorites, custom_lists=lists_with_movies)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))

    cursor = db.database.cursor(dictionary=True)

    # Estadísticas clave
    cursor.execute('SELECT COUNT(*) AS total_movies FROM movies')
    total_movies = cursor.fetchone()['total_movies']

    cursor.execute("SELECT COUNT(*) AS total_users FROM users WHERE role = 'user'")
    total_users = cursor.fetchone()['total_users']

    cursor.execute('SELECT COUNT(*) AS total_comments FROM comments')
    total_comments = cursor.fetchone()['total_comments']

    # Películas más valoradas
    cursor.execute("""
        SELECT 
            m.id, m.title, m.year, m.genre, m.image_url, 
            COALESCE(ROUND(AVG(r.rating), 1), 0) AS average_rating,
            COUNT(r.id) AS total_ratings,
            (SELECT COUNT(*) FROM comments c WHERE c.movie_id = m.id) AS total_comments
        FROM movies m
        LEFT JOIN ratings r ON m.id = r.movie_id
        GROUP BY m.id
    """)

    top_rated_movies = cursor.fetchall()

    # Lista de todas las películas
    cursor.execute('SELECT * FROM movies')
    movies = cursor.fetchall()

    cursor.close()

    return render_template(
        'admin_dashboard.html',
        movies=movies,
        total_movies=total_movies,
        total_users=total_users,
        total_comments=total_comments,
        top_rated_movies=top_rated_movies,
        username=session['username']
    )
    
# Ruta para logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada exitosamente.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)