def register_blueprints(app):
    from routes import (
        auth, profile, students, faculty, departments, courses,
        attendance, results, notices, materials, events, dashboard,
        leaves, assignments,
    )

    app.register_blueprint(auth.bp)
    app.register_blueprint(profile.bp)
    app.register_blueprint(students.bp)
    app.register_blueprint(faculty.bp)
    app.register_blueprint(departments.bp)
    app.register_blueprint(courses.bp)
    app.register_blueprint(attendance.bp)
    app.register_blueprint(results.bp)
    app.register_blueprint(notices.bp)
    app.register_blueprint(materials.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(leaves.bp)
    app.register_blueprint(assignments.bp)
