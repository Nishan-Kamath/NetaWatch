from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from pymongo import MongoClient
from datetime import datetime
import gridfs
import random, string, io
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# ✅ MongoDB Setup
uri = "mongodb+srv://nishankamath:nishankamath@cluster0.emhkoj2.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri)
db = client["neta_watch"]
users = db["users"]
issues = db["issues"]
politicians = db["politicians"]
rti = db["rti"]
reports = db["reports"]
config = db["config"]
fs = gridfs.GridFS(db)

@app.route("/")
def home():
    return render_template("landing.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email_or_phone = request.form.get("email")
        password = request.form.get("password")
        otp = request.form.get("otp")
        plan = request.form.get("plan")
        user = users.find_one({"email_or_phone": email_or_phone})
        if email_or_phone == 'admin' and password=='admin':
            session['user'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        if password:
            if user and user.get("password") == password:
                flash("Login successful with password!", "success")
                session["user"] = email_or_phone
                return redirect(url_for("public_feed"))
            else:
                flash("Invalid password or user not found", "error")
        elif otp:
            flash(f"Login successful with OTP for {email_or_phone}", "success")
            session["user"] = email_or_phone
            return redirect(url_for("public_feed"))

        if not user:
            users.insert_one({
                "email_or_phone": email_or_phone,
                "password": password if password else None,
                "plan": plan,
                "created_at": datetime.utcnow()
            })
            flash("New user registered successfully!", "info")
            session["user"] = email_or_phone
            return redirect(url_for("public_feed"))

    return render_template("login.html")

@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        fullname = request.form['fullname']
        address = request.form['address']
        whatsapp = request.form['whatsapp']
        email_or_phone = request.form['email_or_phone']
        password = request.form['password']
        confirm = request.form['confirm_password']
        plan = request.form['plan']
        profile_file = request.files.get('profile_pic')

        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for('signup'))

        if users.find_one({"email_or_phone": email_or_phone}):
            flash("User already exists. Please login.", "warning")
            return redirect(url_for('login'))

        profile_pic_id = None
        if profile_file and profile_file.filename:
            filename = secure_filename(profile_file.filename)
            profile_pic_id = fs.put(profile_file, filename=filename, content_type=profile_file.content_type)

        users.insert_one({
            "fullname": fullname,
            "address": address,
            "whatsapp": whatsapp,
            "email_or_phone": email_or_phone,
            "password": password,
            "plan": plan,
            "profile_pic_id": profile_pic_id,
            "created_at": datetime.utcnow()
        })

        flash("Account created successfully!", "success")
        session['user'] = email_or_phone
        return redirect(url_for('login'))

    return render_template("signup.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get("user") != "admin":
        flash("Access denied. Admin only.", "danger")
        return redirect(url_for("login"))

    pending_issues = list(issues.find({"status": "pending"}))
    rti_responses = list(rti.find())
    abuse_reports = list(reports.find())
    escalation = config.find_one({"type": "escalation"}) or {"logic": ""}

    all_politicians = list(politicians.find())

    return render_template(
        "admin_dashboard.html",
        issues=pending_issues,
        rti_responses=rti_responses,
        reports=abuse_reports,
        escalation_logic=escalation["logic"],
        politicians=all_politicians  # ✅ Add this
    )


@app.route("/admin/issue/<issue_id>", methods=["POST"])
def admin_approve_issue(issue_id):
    if session.get("user") != "admin":
        return redirect(url_for("login"))

    action = request.form.get("action")
    if action == "approve":
        issues.update_one({"_id": ObjectId(issue_id)}, {"$set": {"status": "approved"}})
        flash("Issue approved!", "success")
    elif action == "delete":
        issues.delete_one({"_id": ObjectId(issue_id)})
        flash("Issue deleted.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/add_politician", methods=["POST"])
def admin_add_politician():
    if session.get("user") != "admin":
        return redirect(url_for("login"))

    name = request.form.get("name")
    region = request.form.get("region")
    role_type = request.form.get("type")
    profile_pic = request.files.get("profile_pic")

    pic_id = None
    if profile_pic and profile_pic.filename:
        filename = secure_filename(profile_pic.filename)
        pic_id = fs.put(profile_pic, filename=filename, content_type=profile_pic.content_type)

    politicians.update_one(
        {"name": name},
        {
            "$set": {
                "region": region,
                "type": role_type,
                "profile_pic_id": pic_id
            }
        },
        upsert=True
    )

    flash("Politician added/updated with details.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete_politician/<id>", methods=["POST"])
def delete_politician(id):
    if session.get("user") != "admin":
        return redirect(url_for("login"))
    politicians.delete_one({"_id": ObjectId(id)})
    flash("Politician deleted.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/edit_politician/<id>", methods=["GET", "POST"])
def edit_politician(id):
    if session.get("user") != "admin":
        return redirect(url_for("login"))
    politician = politicians.find_one({"_id": ObjectId(id)})

    if request.method == "POST":
        updated_data = {
            "name": request.form.get("name"),
            "region": request.form.get("region"),
            "type": request.form.get("type")
        }
        pic = request.files.get("profile_pic")
        if pic and pic.filename:
            filename = secure_filename(pic.filename)
            pic_id = fs.put(pic, filename=filename, content_type=pic.content_type)
            updated_data["profile_pic_id"] = pic_id

        politicians.update_one({"_id": ObjectId(id)}, {"$set": updated_data})
        flash("Politician updated successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("edit_politician.html", p=politician)


@app.route("/admin/update_escalation", methods=["POST"])
def admin_update_escalation():
    if session.get("user") != "admin":
        return redirect(url_for("login"))

    logic = request.form.get("logic")
    config.update_one(
        {"type": "escalation"},
        {"$set": {"logic": logic}},
        upsert=True
    )
    flash("Escalation logic updated.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/report/<report_id>", methods=["POST"])
def admin_handle_report(report_id):
    if session.get("user") != "admin":
        return redirect(url_for("login"))

    action = request.form.get("action")
    report = reports.find_one({"_id": ObjectId(report_id)})
    if not report:
        flash("Report not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if action == "warn":
        reports.update_one({"_id": ObjectId(report_id)}, {"$set": {"status": "warned"}})
        flash("User warned.", "warning")
    elif action == "ban":
        users.update_one({"email_or_phone": report["user"]}, {"$set": {"banned": True}})
        flash("User banned.", "danger")

    return redirect(url_for("admin_dashboard"))


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = users.find_one({"email_or_phone": session['user']})
    user_issues = issues.find({"reported_by": session['user']})

    # ✅ Convert profile_pic_id to string
    if user and 'profile_pic_id' in user and user['profile_pic_id']:
        user['profile_pic_id'] = str(user['profile_pic_id'])

    return render_template("dashboard.html", user=user, user_issues=user_issues)


@app.route('/profile-pic/<file_id>')
def serve_profile_pic(file_id):
    try:
        file = fs.get(ObjectId(file_id))
        return send_file(
            io.BytesIO(file.read()),
            mimetype=file.content_type,
            download_name=file.filename  # optional, helps debugging
        )
    except Exception as e:
        print("⚠️ Profile pic error:", e)
        return "Profile picture not found", 404

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/report", methods=["GET", "POST"])
def report():
    if "user" not in session:
        flash("Login required to report an issue.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        media_file = request.files["media"]
        filename = secure_filename(media_file.filename)
        file_id = fs.put(media_file, filename=filename, content_type=media_file.content_type)

        track_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        description = request.form["description"]

        issue = {
            "reported_by": session["user"],
            "category": request.form["category"],
            "description": description,  # includes \n and emojis
            "location": request.form["location"],
            "matched_politician": "Ward → MLA → MP (placeholder)",
            "media_file_id": file_id,
            "track_id": track_id,
            "created_at": datetime.utcnow(),
            "likes": [],
            "comments": [],
            "status": "pending"
        }

        issues.insert_one(issue)
        flash(f"Issue submitted successfully! Track ID: {track_id}", "success")
        return redirect(url_for("report"))

    return render_template("report_issue.html")


@app.route('/media/<file_id>')
def serve_media(file_id):
    try:
        file = fs.get(ObjectId(file_id))
        return send_file(io.BytesIO(file.read()), mimetype=file.content_type)
    except:
        return "Image not found", 404

@app.route("/feed")
def public_feed():
    category = request.args.get("category")
    status = request.args.get("status")
    region = request.args.get("region")

    query = {}
    if category:
        query["category"] = category
    if status:
        query["status"] = status
    if region:
        query["location"] = {"$regex": region, "$options": "i"}

    all_issues = issues.find(query).sort("created_at", -1)

    issues_list = []
    for issue in all_issues:
        issue["_id"] = str(issue["_id"])
        if "media_file_id" in issue:
            issue["media_file_id"] = str(issue["media_file_id"])
        issue.setdefault("likes", [])
        issue.setdefault("comments", [])
        issues_list.append(issue)

    return render_template("public_feed.html", issues=issues_list)

@app.route("/like/<issue_id>", methods=["POST"])
def like_issue(issue_id):
    user = session.get("user")
    if not user:
        return {"success": False, "message": "Login required"}, 403

    issue = issues.find_one({"_id": ObjectId(issue_id)})
    if not issue:
        return {"success": False, "message": "Issue not found"}, 404

    if user in issue.get("likes", []):
        issues.update_one({"_id": ObjectId(issue_id)}, {"$pull": {"likes": user}})
        liked = False
    else:
        issues.update_one({"_id": ObjectId(issue_id)}, {"$addToSet": {"likes": user}})
        liked = True

    updated = issues.find_one({"_id": ObjectId(issue_id)})
    return {"success": True, "liked": liked, "like_count": len(updated["likes"])}

@app.route("/comment/<issue_id>", methods=["POST"])
def comment_issue(issue_id):
    user = session.get("user")
    text = request.form.get("text")

    if not user or not text:
        return {"success": False}, 400

    comment = {"user": user, "text": text, "timestamp": datetime.utcnow()}
    issues.update_one({"_id": ObjectId(issue_id)}, {"$push": {"comments": comment}})
    return redirect(url_for("public_feed"))

polls_collection = db["polls"]

@app.route("/polls", methods=["GET"])
def polls():
    user_email = session.get("user")
    if not user_email:
        flash("Login required to access polls.", "warning")
        return redirect(url_for("login"))

    user = users.find_one({"email_or_phone": user_email})
    is_verified = user.get("plan", "") in ["Verified", "Prime"]

    all_polls = list(polls_collection.find())
    for p in all_polls:
        p["_id"] = str(p["_id"])
        p["votes"] = p.get("votes", [0, 0])
        p["comments"] = p.get("comments", [])
    return render_template("polls.html", user_verified=is_verified, polls=all_polls)

@app.route("/create_poll", methods=["POST"])
def create_poll():
    if "user" not in session:
        return redirect(url_for("login"))
    question = request.form.get("question")
    options = [request.form.get("option1"), request.form.get("option2")]
    polls_collection.insert_one({"question": question, "options": options, "votes": [0]*len(options), "comments": []})
    return redirect("/polls")

@app.route("/vote/<poll_id>", methods=["POST"])
def vote(poll_id):
    selected_option = request.form.get("option")
    poll = polls_collection.find_one({"_id": ObjectId(poll_id)})
    if poll:
        index = poll["options"].index(selected_option)
        poll["votes"][index] += 1
        polls_collection.update_one({"_id": ObjectId(poll_id)}, {"$set": {"votes": poll["votes"]}})
    return redirect("/polls")

@app.route("/poll_comment/<poll_id>", methods=["POST"])
def poll_comment(poll_id):
    comment = request.form.get("comment")
    polls_collection.update_one({"_id": ObjectId(poll_id)}, {"$push": {"comments": comment}})
    return redirect("/polls")


if __name__ == "__main__":
    app.run(debug=True)
