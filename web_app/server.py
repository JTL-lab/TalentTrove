from crypt import methods
import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, flash, request, render_template, g, redirect, Response, url_for

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

# ADD DATABASE CREDENTIALS HERE BEFORE RUNNING; DO NOT PUSH
DATABASE_USERNAME = ""
DATABASE_PASSWRD = ""
DATABASE_HOST = "35.212.75.104"
DATABASEURI = f"postgresql://{DATABASE_USERNAME}:{DATABASE_PASSWRD}@{DATABASE_HOST}/proj1part2"

# Create database engine
engine = create_engine(DATABASEURI)  # noqa: F405

# Example query in database
with engine.connect() as conn:
    create_table_command = """
    CREATE TABLE IF NOT EXISTS test (
        id serial,
        name text
    )
    """
    res = conn.execute(text(create_table_command))
    insert_table_command = """INSERT INTO test(name) VALUES ('grace hopper'), ('alan turing'), ('ada lovelace')"""
    res = conn.execute(text(insert_table_command))
    # you need to commit for create, insert, update queries to reflect
    conn.commit()

@app.before_request
def before_request():
    """
    This function is run at the beginning of every web request
    (every time you enter an address in the web browser).
    We use it to setup a database connection that can be used throughout the request.

    The variable g is globally accessible.
    """
    try:
        g.conn = engine.connect()
    except:
        print("uh oh, problem connecting to database")
        import traceback; traceback.print_exc()
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't, the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception as e:
        pass

@app.route('/')
def index():
    """
    request is a special object that Flask provides to access web request information:

    request.method:   "GET" or "POST"
    request.form:     if the browser submitted a form, this contains the data in the form
    request.args:     dictionary of URL arguments, e.g., {a:1, b:2} for http://localhost?a=1&b=2

    See its API: https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data
    """

    # DEBUG: this is debugging code to see what request looks like
    print(request.args)

    # example database query
    select_query = "SELECT username from candidate where username='pashlin0'"
    cursor = g.conn.execute(text(select_query))
    names = []
    for result in cursor:
        names.append(result[0])
    cursor.close()

    context = dict(data = names)

    return render_template("index.html", **context)


# Example of adding new data to the database
@app.route('/add', methods=['POST'])
def add():
    # accessing form inputs from user
    name = request.form['name']

    # passing params in for each variable into query
    params = {}
    params["new_name"] = name
    g.conn.execute(text('INSERT INTO test(name) VALUES (:new_name)'), params)
    g.conn.commit()
    return redirect('/')


@app.route('/login')
def login():
    pass

@app.route('/job_board',methods=('GET','POST'))
def job_board():

    # Default query (i.e. what is executed if user does not select anything specific to filter by)
    base_search_query = """SELECT j.Job_ID, j.Job_Title, j.Experience, j.Location, j.Requirements, j.Skills, 
                                   c.Name as Company_Name, r.Name as Recruiter_Name
                                   FROM Job_Posting j
                                   JOIN Company c ON j.Company_ID = c.Company_ID
                                   JOIN Recruiter r ON j.Recruiter_Username = r.Username
    """
    if request.method == "POST":

        # Collect all user selected field values
        location = request.form.get('Location', '')
        company = request.form.get('Company', '')
        skills = request.form.get('Skills', '')
        search = request.form.get('Search', '')
        experience = request.form.get('Experience', '')
        role_types = request.form.getlist('role_types')

        # Keep track of all user selected fields to filter by to build SQL query
        where_clauses = []
        params = {}

        # Collect user selected field values
        if location:
            where_clauses.append("j.location LIKE :location")
            params['location'] = "%" + location + "%"

        if company:
            where_clauses.append("c.Name LIKE :company")
            params['company'] = "%" + company + "%"

        if skills:
            where_clauses.append("j.Skills LIKE :skills")
            params['skills'] = "%" + skills + "%"

        if experience:
            where_clauses.append("j.Experience LIKE :experience")
            params['experience'] = "%" + experience + "%"

        if role_types:
            # Depending on the role type selected, need to select jobs from the corresponding table
            role_queries = []
            if 'full_time' in role_types:
                role_queries.append("j.Job_ID IN (SELECT Job_ID FROM Full_Time_Job)")
            if 'internship' in role_types:
                role_queries.append("j.Job_ID IN (SELECT Job_ID FROM Internship_Job)")
            if 'coop' in role_types:
                role_queries.append("j.Job_ID IN (SELECT Job_ID FROM Co_Op_Job)")
            where_clauses.append("(" + " OR ".join(role_queries) + ")")

        if search:
            # If user is searching, set up filter query statements based on the keywords they entered
            search_clauses = " OR ".join([
                "j.location LIKE :search",
                "c.Name LIKE :search",
                "j.Skills LIKE :search",
                "j.Job_Title LIKE :search",
                "j.Experience LIKE :search",
                "j.Requirements LIKE :search",
                "r.Name LIKE :search"
            ])
            where_clauses.append(f"({search_clauses})")
            params["search"] = "%" + search + "%"

        # Check which query to execute: query with user selected params if any, and if not any then default to show all
        if where_clauses:
            full_query = base_search_query + " WHERE " + " AND ".join(where_clauses)
        else:
            full_query = base_search_query

        # Execute query
        cursor = g.conn.execute(text(full_query), params)
        postings = cursor.fetchall()
        cursor.close()

        return render_template('job_board.html',postings=postings)

    # On GET or if no filter is applied, show all postings
    cursor = g.conn.execute(text(base_search_query))
    postings = cursor.fetchall()
    cursor.close()

    return render_template('job_board.html')


@app.route('/post_job', methods=['GET', 'POST'])
def post_job():
    if request.method == 'POST':

        # Collect form data
        job_id = request.form['Job_ID']
        job_title = request.form['Job_Title']
        experience = request.form['Experience']
        location = request.form['Location']
        requirements = request.form['Requirements']
        skills = request.form['Skills']
        company_id = request.form['Company_ID']
        recruiter_username = request.form['Recruiter_Username']
        job_type = request.form['job_type']

        # Look up the portal_id for the company entered and automatically link job with that portal
        portal_query = """SELECT Portal_ID 
                          FROM Job_Portal 
                          WHERE Company_ID = :company_id
        """
        portal_result = g.conn.execute(text(portal_query), {'company_id': company_id}).fetchone()
        portal_id = portal_result[0]

        # First add new role as row in Job_Posting table
        insert_query = """INSERT INTO Job_Posting (Job_ID, Job_Title, Experience, Location, Requirements, Skills, 
                          Company_ID, Recruiter_Username, Portal_ID)
                          VALUES (:job_id, :job_title, :experience, :location, :requirements, :skills, :company_id, 
                          :recruiter_username, :portal_id)
        """
        g.conn.execute(text(insert_query), {
            'job_id': job_id,
            'job_title': job_title,
            'experience': experience,
            'location': location,
            'requirements': requirements,
            'skills': skills,
            'company_id': company_id,
            'recruiter_username': recruiter_username,
            'portal_id': portal_id
        })
        # Need this to ensure transaction updates table
        g.conn.commit()

        # Secondly also add other table specific information depending on if role is full time, internship, or coop job
        if job_type == 'full_time':
            annual_salary = request.form['AnnualSalary']
            insert_query = "INSERT INTO Full_Time_Job (Job_ID, AnnualSalary) VALUES (:job_id, :annual_salary)"
            g.conn.execute(text(insert_query), {
                'job_id': job_id,
                'annual_salary': annual_salary
            })
            g.conn.commit()

        elif job_type == 'internship':
            duration = request.form['Duration']
            salaried = request.form['Salaried'] == 'true'
            insert_query = "INSERT INTO Internship_Job (Job_ID, Duration, Salaried) VALUES (:job_id, :duration, :salaried)"
            g.conn.execute(text(insert_query), {
                'job_id': job_id,
                'duration': duration,
                'salaried': salaried
            })
            g.conn.commit()

        elif job_type == 'coop':
            duration = request.form['Duration']
            salaried = request.form['Salaried'] == 'true'
            coop_type = request.form['Type']
            insert_query = "INSERT INTO Co_Op_Job (Job_ID, Duration, Salaried, Type) VALUES (:job_id, :duration, :salaried, :coop_type)"
            g.conn.execute(text(insert_query), {
                'job_id': job_id,
                'duration': duration,
                'salaried': salaried,
                'coop_type': coop_type
            })
            g.conn.commit()

		# Redirect the recruiter back to the job_board after they've added the new role!
        return redirect(url_for('job_board'))

    return render_template('post_job.html')


@app.route('/reviews')
def reviews():
    # Will have two separate tables on the reviews page: one for candidate reviews, one for employee reviews
    interview_reviews_query = """SELECT Review_ID, Interview_Feedback 
                               FROM Review 
                               WHERE Interview_Feedback IS NOT NULL"""
    company_reviews_query = """SELECT Review_ID, Company_Feedback 
                               FROM Review 
                               WHERE Company_Feedback IS NOT NULL"""
    interview_reviews = g.conn.execute(text(interview_reviews_query)).fetchall()
    print(interview_reviews)
    company_reviews = g.conn.execute(text(company_reviews_query)).fetchall()
    print(company_reviews)
    return render_template("reviews.html", interview_reviews=interview_reviews, company_reviews=company_reviews)


if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

run()
