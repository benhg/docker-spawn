from flask import Flask, render_template, request, redirect, session, url_for
import time
from werkzeug import secure_filename
from functools import wraps
import os
import glob
import uuid
import json
import sqlite3
import hashlib

app = Flask(__name__)

app.config['db_conn'] = sqlite3.connect("interface.db")
app.config["db_cursor"] = app.config['db_conn'].cursor()
app.config['upload_base_dir'] = "/Users/ben/Google Drive/class/y2/ind_study/workspace/uploads/"
app.secret_key = b'\x9b4\xf8%\x1b\x90\x0e[?\xbd\x14\x7fS\x1c\xe7Y\xd8\x1c\xf9\xda\xb0K=\xba'
# I will obviously change this secret key before we go live


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_auth(session.get('username', None)):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


@app.route('/')
@app.route('/index')
@app.route('/index.html')
@app.route('/index.php')
@app.route('/home')
@app.route('/home.html')
def hello_world():
    return render_template("home.html")


@app.route('/filesystem_generator')
def fs_gen():
    raise NotImplementedError


@app.route('/job<jid>')
def status_page(jid):
    return "Status Page"


@app.route('/login')
def login():
    return render_template("login.html")


@app.route('/login_test', methods=["POST"])
def login_test():
    uname = request.form['uname']
    passwd = hashlib.sha224(request.form['passwd'].encode('utf-8')).hexdigest()
    print(uname, passwd)
    record = app.config['db_cursor'].execute(
        "select * from users where username=?", (uname,)).fetchone()
    if record:
        if passwd == record[4]:
            session['username'] = uname
            session["display_name"] = record[3]
            session['uuid'] = record[1]
            return "pass"
    return "fail"


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("hello_world"))


@app.route('/authcallback')
def authcallback():
    raise NotImplementedError


@app.route('/howto')
@app.route('/help')
def help():
    raise NotImplementedError


@app.route('/about')
def about():
    raise NotImplementedError


@app.route('/myjobs')
@requires_auth
def all_jobs2():
    uname = session.get('display_name')
    alljobs = app.config["db_cursor"].execute(
        """select job_name, display_name, cli_invoc, time_created, status, size,
        time_finished, desc
        from jobs
        join users on jobs.creator_uuid=users.user_uuid
        where users.user_uuid=?""", (session.get('uuid'),)).fetchall()
    return render_template("all_my_jobs.html", all_jobs=alljobs, u_name=uname)


@app.route('/jobs')
@requires_auth
def all_jobs():
    alljobs = app.config["db_cursor"].execute(
        """select job_name, display_name, cli_invoc, time_created, status, size,
        time_finished, desc
        from jobs
        join users on jobs.creator_uuid=users.user_uuid""").fetchall()
    return render_template("all_jobs.html", all_jobs=alljobs)


@app.route('/newjob')
@requires_auth
def submit_page():
    print(session)
    return render_template('submit.html')


def sanitize_for_filename(filename):
    keepcharacters = [' ', '.', '_']
    safe = "".join(c for c in filename if c.isalnum()
                   or c in keepcharacters).rstrip()
    return safe.replace(" ", "_")


def db_save_job(jn, fn, cli, u_uuid, desc, b_dir):
    job_uuid = str(uuid.uuid1())
    now = str(time.ctime())
    app.config['db_cursor'].execute("""insert into jobs (job_name, cli_invoc, 
    time_created, j_id, creator_uuid, status, base_dir,
    exe_filename, size, desc) VALUES (?,?,?,?,?,?,?,?,?,?) """, (
        jn, cli, now, job_uuid, u_uuid, "Pending", b_dir, fn, 1, desc)
    )
    app.config['db_conn'].commit()


@app.route('/script', methods=["POST"])
@requires_auth
def script_handler():
    jn = sanitize_for_filename(
        dict(request.form).get('job_name', ["job"])[0])
    fn = sanitize_for_filename(
        dict(request.form).get('filename', ['script'])[0])
    fs = dict(request.files).get("filestructure", [None])[0]
    script = dict(request.files).get("executable", [None])[0]
    desc = request.form.get("desc", [None])
    cli = request.form.get("cli", [None])
    jn, b_dir = make_job_base_dir(fn, jn, script)
    db_save_job(jn, fn, cli,
                session["uuid"], desc, b_dir)
    if fs:
        fs.save(app.config["upload_base_dir"] +
                jobname + "/filestructure.json")
        parse_filesystem(jobname)
    return redirect('/newjob')


def make_job_base_dir(filename, jobname, script):
    if not os.path.exists(app.config['upload_base_dir'] + jobname):
        os.makedirs(app.config['upload_base_dir'] +
                    sanitize_for_filename(jobname))
    else:
        full_job_name_list = (
            app.config['upload_base_dir'] + jobname).split("_")[:-1]
        full_job_name = '_'.join(full_job_name_list) + "*"
        numruns = str(len(glob.glob(full_job_name)) + 1)
        print(numruns)
        jobname = jobname + "_" + numruns
        os.makedirs(app.config['upload_base_dir'] +
                    sanitize_for_filename(jobname))
    script.save(app.config['upload_base_dir'] + jobname + "/" + filename)
    return jobname, app.config['upload_base_dir'] + sanitize_for_filename(jobname)


def parse_filesystem(jobname):
    dirpath = app.config["upload_base_dir"] + jobname + "/"
    try:
        fs_desc = json.load(open((dirpath + "filestructure.json", "r")))
    except Exception as e:
        app.logger.info("No FS_desc provided for job {}".format(jobname))
    for object in fs_desc():
        pass


def check_auth(username):
    """This function is called to check if a username /
    password combination is valid.
    """
    print(username)
    record = app.config['db_cursor'].execute(
        "select * from users where username=?", (username,)).fetchone()
    if not record:
        return False
    return username == record[0]


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return render_template("autherr.html")
