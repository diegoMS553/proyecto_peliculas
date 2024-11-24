import database as db

def get_movie_rating(movie_id):
    cursor = db.database.cursor(dictionary=True)  # Usar dictionary=True
    cursor.execute("""
        SELECT AVG(rating) AS average_rating, COUNT(rating) AS total_ratings
        FROM ratings WHERE movie_id = %s
    """, (movie_id,))
    result = cursor.fetchone()  # Resultado como diccionario
    cursor.close()

    if result:
        return result['average_rating'], result['total_ratings']
    return None, 0
