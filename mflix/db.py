"""
This module contains all database interfacing methods for the MFlix
application. You will be working on this file for the majority of M220P.

Each method has a short description, and the methods you must implement have
docstrings with a short explanation of the task.

Look out for TODO markers for additional help. Good luck!
"""


from flask import current_app, g
from werkzeug.local import LocalProxy

from pymongo import MongoClient, DESCENDING
from pymongo.write_concern import WriteConcern
from pymongo.errors import DuplicateKeyError, OperationFailure
from bson.objectid import ObjectId
from bson.errors import InvalidId
from pymongo.read_concern import ReadConcern


def get_db():
    """
    Configuration method to return db instance
    """
    db = getattr(g, "_database", None)
    MFLIX_DB_URI = current_app.config["MFLIX_DB_URI"]
    if db is None:

        """
        Ticket: Connection Pooling

        Please change the configuration of the MongoClient object by setting the
        maximum connection pool size to 50 active connections.
        """

        """
        Ticket: Timeouts

        Please prevent the program from waiting indefinitely by setting the
        write concern timeout limit to 2500 milliseconds.
        """

        db = g._database = MongoClient(
        MFLIX_DB_URI,
        maxPoolSize=50,
        wtimeout=2500,
        # TODO: Connection Pooling
        # Set the maximum connection pool size to 50 active connections.
        # TODO: Timeouts
        # Set the write timeout limit to 2500 milliseconds.
        )["mflix"]
    return db


# Use LocalProxy to read the global db instance with just `db`
db = LocalProxy(get_db)


def get_movies_by_country(countries):
    """
    Finds and returns movies by country.
    Returns a list of dictionaries, each dictionary contains a title and an _id.
    """
    try:

        """
        Ticket: Projection

        Write a query that matches movies with the countries in the "countries"
        list, but only returns the title and _id of each movie.

        Remember that in MongoDB, the $in operator can be used with a list to
        match one or more values of a specific field.
        """

        # TODO: Projection
        # Find movies matching the "countries" list, but only return the title
        # and _id.
        return list(db.movies.find({"countries": {"$in": countries}},{"title":1}))

    except Exception as e:
        return e


def get_movies_faceted(filters, page, movies_per_page):
    """
    Returns movies and runtime and ratings facets. Also returns the total
    movies matched by the filter.

    Uses the same sort_key as get_movies
    """
    sort_key = "tomatoes.viewer.numReviews"

    pipeline = []

    if "cast" in filters:
        pipeline.extend([{
            "$match": {"cast": {"$in": filters.get("cast")}}
        }, {
            "$sort": {sort_key: DESCENDING}
        }])
    else:
        raise AssertionError("No filters to pass to faceted search!")

    counting = pipeline[:]
    count_stage = {"$count": "count"}
    counting.append(count_stage)

    skip_stage = {"$skip": movies_per_page * page}
    limit_stage = {"$limit": movies_per_page}
    facet_stage = {
        "$facet": {
            "runtime": [{
                "$bucket": {
                    "groupBy": "$runtime",
                    "boundaries": [0, 60, 90, 120, 180],
                    "default": "other",
                    "output": {
                        "count": {"$sum": 1}
                    }
                }
            }],
            "rating": [{
                "$bucket": {
                    "groupBy": "$metacritic",
                    "boundaries": [0, 50, 70, 90, 100],
                    "default": "other",
                    "output": {
                        "count": {"$sum": 1}
                    }
                }
            }],
            "movies": [{
                "$addFields": {
                    "title": "$title"
                }
            }]
        }
    }

    """
    Ticket: Faceted Search

    Please append the skip_stage, limit_stage, and facet_stage to the pipeline
    (in that order).

    The pipeline is a Python array, so you can use append() or extend() to
    complete this task.
    """

    # TODO: Faceted Search
    # Add the necessary stages to the pipeline variable in the correct order.
    #pipeline = []
    pipeline.append(skip_stage)
    pipeline.append(limit_stage)
    pipeline.append(facet_stage)
    try:
        movies = list(db.movies.aggregate(pipeline, allowDiskUse=True))[0]
        count = list(db.movies.aggregate(counting, allowDiskUse=True))[
            0].get("count")
        return (movies, count)
    except OperationFailure:
        raise OperationFailure(
            "Results too large to sort, be more restrictive in filter")


def build_query_sort_project(filters):
    """
    Builds the `query` predicate, `sort` and `projection` attributes for a given
    filters dictionary.
    """
    query = {}
    # The field "tomatoes.viewer.numReviews" only exists in the movies we want
    # to display on the front page of MFlix, because they are famous or
    # aesthetically pleasing. When we sort on it, the movies containing this
    # field will be displayed at the top of the page.
    sort = [("tomatoes.viewer.numReviews", DESCENDING)]
    project = None
    if filters:
        if "text" in filters:
            query = {"$text": {"$search": filters["text"]}}
            meta_score = {"$meta": "textScore"}
            sort = [("score", meta_score)]
            project = {"score": meta_score}
        elif "cast" in filters:
            query = {"cast": {"$in": filters["cast"]}}
        elif "genres" in filters:

            """
            Ticket: Text and Subfield Search

            Given a genre in the "filters" object, construct a query that
            searches MongoDB for movies with that genre.
            """

            # TODO: Text and Subfield Search
            # Construct a query that will search for the chosen genre.
            query = {"genres": {"$in": filters["genres"]}}

    return query, sort, project


def get_movies(filters, page, movies_per_page):
    """
    Returns a cursor to a list of movie documents.

    Based on the page number and the number of movies per page, the result may
    be skipped and limited.

    The `filters` from the API are passed to the `build_query_sort_project`
    method, which constructs a query, sort, and projection, and then that query
    is executed by this method (`get_movies`).

    Returns 2 elements in a tuple: (movies, total_num_movies)
    """
    query, sort, project = build_query_sort_project(filters)
    if project:
        cursor = db.movies.find(query, project).sort(sort)
    else:
        cursor = db.movies.find(query).sort(sort)

    total_num_movies = 0
    if page == 0:
        total_num_movies = db.movies.count_documents(query)
    """
    Ticket: Paging

    Before this method returns back to the API, use the "movies_per_page"
    argument to decide how many movies get displayed per page. The "page"
    argument will decide which page

    Paging can be implemented by using the skip() and limit() methods against
    the Pymongo cursor.
    """

    # TODO: Paging
    # Use the cursor to only return the movies that belong on the current page.
    movies = cursor.limit(movies_per_page).skip(page*movies_per_page)

    return (list(movies), total_num_movies)


def get_movie(id):
    """
    Given a movie ID, return a movie with that ID, with the comments for that
    movie embedded in the movie document. The comments are joined from the
    comments collection using expressive $lookup.
    """

    try:

        """
        Ticket: Get Comments

        Please implement a $lookup stage in this pipeline to find all the
        comments for the given movie. The movie_id in the `comments` collection
        can be used to refer to the _id from the `movies` collection.

        Embed the joined comments in a new field called "comments".
        """

        # TODO: Get Comments
        # Implement the required pipeline.
        pipeline = [
            {
                "$match": {
                    "_id": ObjectId(id)
                }
            },
            {
                "$lookup": {
                    "from": "comments",
                    "localField": "_id",
                    "foreignField": "movie_id",
                    "as": "comments"
                }        
            }
        ]

        movie = db.movies.aggregate(pipeline).next()
        return movie

        # TODO: Error Handling
        # If an invalid ID is passed to `get_movie`, it should return None.
    # except (StopIteration) as _:
    except InvalidId as e:

        """
        Ticket: Error Handling

        Handle the InvalidId exception from the BSON library the same way as the
        StopIteration exception is handled. Both exceptions should result in
        `get_movie` returning None.
        """

        return None


def get_all_genres():
    """
    Returns list of all genres in the database.
    """
    return list(db.movies.aggregate([
        {"$unwind": "$genres"},
        {"$group": {"_id": None, "genres": {"$addToSet": "$genres"}}}
    ]))[0]["genres"]


"""
Ticket: Create/Update Comments

For this ticket, you will need to implement the following two methods:

- add_comment
- update_comment

You can find these methods below this docstring. Make sure to read the comments
to better understand the task.
"""


def add_comment(movie_id, user, comment, date):
    """
    Inserts a comment into the comments collection, with the following fields:

    - "name"
    - "email"
    - "movie_id"
    - "text"
    - "date"

    Name and email must be retrieved from the "user" object.
    """
    # TODO: Create/Update Comments
    # Construct the comment document to be inserted into MongoDB.
    comment_doc = {"name":user.name,"email":user.email,"movie_id":ObjectId(movie_id),"text":comment,"date":date}
    return db.comments.insert_one(comment_doc)


def update_comment(comment_id, user_email, text, date):
    """
    Updates the comment in the comment collection. Queries for the comment
    based by both comment _id field as well as the email field to doubly ensure
    the user has permission to edit this comment.
    """
    # TODO: Create/Update Comments
    # Use the user_email and comment_id to select the proper comment, then
    # update the "text" and "date" of the selected comment.
    response = db.comments.update_one({"_id": ObjectId(comment_id),"email":user_email}, {"$set": {"text": text,"date": date}})

    return response


def delete_comment(comment_id, user_email):
    """
    Given a user's email and a comment ID, deletes a comment from the comments
    collection
    """

    """
    Ticket: Delete Comments

    Match the comment_id and user_email with the correct fields, to make sure
    this user has permission to delete this comment, and then delete it.
    """

    # TODO: Delete Comments
    # Use the user_email and comment_id to delete the proper comment.
    response = db.comments.delete_one(
        {"_id": ObjectId(comment_id),"email":user_email}
    )
    return response


"""
Ticket: User Management

For this ticket, you will need to implement the following six methods:

- get_user
- add_user
- login_user
- logout_user
- get_user_session
- delete_user

You can find these methods below this docstring. Make sure to read the comments
to better understand the task.
"""


def get_user(email):
    """
    Given an email, returns a document from the `users` collection.
    """
    # TODO: User Management
    # Retrieve the user document corresponding with the user's email.
    return db.users.find_one({"email": email})


def add_user(name, email, hashedpw):
    """
    Given a name, email and password, inserts a document with those credentials
    to the `users` collection.
    """

    """
    Ticket: Durable Writes

    Please increase the durability of this method by using a non-default write
    concern with ``insert_one``.
    """

    try:
        # TODO: User Management
        # Insert a user with the "name", "email", and "password" fields.
        # TODO: Durable Writes
        # Use a more durable Write Concern for this operation.
        db.users.insert_one({"name": name,"email": email,"password": hashedpw,"writeConcern":{"w":"majority"}})
        return {"success": True}
    except DuplicateKeyError:
        return {"error": "A user with the given email already exists."}


def login_user(email, jwt):
    """
    Given an email and JWT, logs in a user by updating the JWT corresponding
    with that user's email in the `sessions` collection.

    In `sessions`, each user's email is stored in a field called "user_id".
    """
    try:
        # TODO: User Management
        # Use an UPSERT statement to update the "jwt" field in the document,
        # matching the "user_id" field with the email passed to this function.
        db.sessions.update_one({"user_id": email}, {"$set": {"jwt": jwt}})
        return {"success": True}
    except Exception as e:
        return {"error": e}


def logout_user(email):
    """
    Given a user's email, logs out that user by deleting their corresponding
    entry in the `sessions` collection.

    In `sessions`, each user's email is stored in a field called "user_id".
    """
    try:
        # TODO: User Management
        # Delete the document in the `sessions` collection matching the email.
        db.sessions.delete_one({"user_id": email})
        return {"success": True}
    except Exception as e:
        return {"error": e}


def get_user_session(email):
    """
    Given a user's email, finds that user's session in `sessions`.

    In `sessions`, each user's email is stored in a field called "user_id".
    """
    try:
        # TODO: User Management
        # Retrieve the session document corresponding with the user's email.
        return db.sessions.find_one({"user_id": email})
    except Exception as e:
        return {"error": e}


def delete_user(email):
    """
    Given a user's email, deletes a user from the `users` collection and deletes
    that user's session from the `sessions` collection.
    """
    try:
        # TODO: User Management
        # Delete the corresponding documents from `users` and `sessions`.
        db.sessions.delete_one({"user_id": email})
        db.users.delete_one({"email": email})
        if get_user(email) is None:
            return {"success": True}
        else:
            raise ValueError("Deletion unsuccessful")
    except Exception as e:
        return {"error": e}


def update_prefs(email, prefs):
    """
    Given a user's email and a dictionary of preferences, update that user's
    preferences.
    """
    prefs = {} if prefs is None else prefs
    try:

        """
        Ticket: User Preferences

        Update the "preferences" field in the corresponding user's document to
        reflect the information in prefs.
        """

        # TODO: User preferences
        # Use the data in "prefs" to update the user's preferences.
        response = db.users.update_one({"email": email}, {"$set": {"preferences": prefs}})
        if response.matched_count == 0:
            return {'error': 'no user found'}
        else:
            return response
    except Exception as e:
        return {'error': str(e)}


def most_active_commenters():
    """
    Returns a list of the top 20 most frequent commenters.
    """

    """
    Ticket: User Report

    Construct a pipeline to find the users who comment the most on MFlix, sort
    by the number of comments, and then only return the 20 documents with the
    highest values.

    No field projection necessary.
    """
    # TODO: User Report
    # Return the 20 users who have commented the most on MFlix.
    pipeline = []
    group_stage = {
        "$group": {
        "_id": "$email"
            ,
        "count": { "$sum": 1 }
        }
    }
    sort_stage = {
        "$sort": { "count": -1 }
    }
    limit_stage={ "$limit": 20 }
    pipeline = [
        group_stage,
        sort_stage,
        limit_stage
    ]
    rc = ReadConcern(level='majority') # you may want to change this read concern!
    comments = db.comments.with_options(read_concern=rc)
    result = comments.aggregate(pipeline)
    return list(result)


def make_admin(email):
    """
    Supplied method
    Flags the supplied user an an admin
    """
    db.users.update_one({"email": email}, {"$set": {"isAdmin": True}})


def get_configuration():
    """
    Returns the following information configured for this client:

    - max connection pool size
    - write concern
    - database user role
    """
    role_info = db.command({'connectionStatus': 1}).get('authInfo').get(
        'authenticatedUserRoles')[0]
    return (db.client.max_pool_size, db.client.write_concern, role_info)
