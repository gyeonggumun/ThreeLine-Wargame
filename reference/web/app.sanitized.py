import hashlib
import hmac
import subprocess

from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pymysql

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
)


app = Flask(__name__)


# ==========================================================
# MariaDB 설정
# ==========================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "wargame_user",
    "password": "<REDACTED_LAB_DB_PASSWORD>",
    "db": "wargame_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}


# ==========================================================
# 중앙 진행도 기록 함수
# ==========================================================

def mark_progress(
    participant_id: str,
    challenge_id: int,
    flag_id: int
) -> bool:
    """
    중앙 진행도 API에 Challenge 완료 상태를 기록한다.
    """

    if not participant_id:
        return False

    if len(participant_id) != 32:
        return False

    try:
        int(participant_id, 16)

    except ValueError:
        return False

    secret_path = (
        "/etc/wargame-progress/secret.key"
    )

    try:
        with open(
            secret_path,
            "r",
            encoding="utf-8"
        ) as secret_file:
            secret = secret_file.read().strip()

        if not secret:
            return False

        message = (
            f"{participant_id}|"
            f"{challenge_id}|"
            f"{flag_id}"
        )

        signature = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        post_data = urlencode({
            "participant_id": participant_id,
            "challenge_id": challenge_id,
            "flag_id": flag_id,
            "signature": signature
        }).encode("utf-8")

        progress_request = Request(
            "http://127.0.0.1/"
            "progress/complete.php",
            data=post_data,
            method="POST",
            headers={
                "Content-Type":
                    "application/"
                    "x-www-form-urlencoded"
            }
        )

        with urlopen(
            progress_request,
            timeout=3
        ) as response:
            return 200 <= response.status < 300

    except Exception as error:
        print(
            "[Progress] Record failed: "
            f"{error}",
            flush=True
        )

        return False


# ==========================================================
# 메인 페이지
# ==========================================================

@app.route("/")
def index():
    return render_template(
        "index.html"
    )


# ==========================================================
# Challenge 1
# JSON Blind SQL Injection
# ==========================================================

@app.route("/ch1")
def ch1_page():
    return render_template(
        "ch1.html"
    )


@app.route(
    "/api/ch1/login",
    methods=["POST"]
)
def ch1_login():
    data = request.get_json(
        silent=True
    )

    if not data:
        return jsonify({
            "status": "error",
            "message": "JSON 형식이어야 합니다."
        }), 400

    username = data.get(
        "username",
        ""
    )

    password = data.get(
        "password",
        ""
    )

    # 의도적인 SQL Injection 취약점
    query = (
        "SELECT * FROM users "
        f"WHERE username = '{username}' "
        f"AND password = '{password}'"
    )

    connection = None

    try:
        connection = pymysql.connect(
            **DB_CONFIG
        )

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        if result:
            if result.get("username") == "admin":
                participant_id = (
                    request.cookies.get(
                        "participant_id",
                        ""
                    )
                )

                mark_progress(
                    participant_id,
                    1,
                    1
                )

            return jsonify({
                "status": "success",
                "message": "로그인 성공!"
            })

        return jsonify({
            "status": "fail",
            "message":
                "로그인 실패: 계정 정보가 틀렸습니다."
        })

    except Exception as error:
        print(
            f"[Challenge 1] {error}",
            flush=True
        )

        return jsonify({
            "status": "error",
            "message": "서버 내부 오류 발생"
        }), 500

    finally:
        if connection is not None:
            connection.close()


# ==========================================================
# Challenge 2
# Blind OS Command Injection
# ==========================================================

@app.route("/ch2")
def ch2_page():
    participant_id = (
        request.cookies.get(
            "participant_id",
            ""
        )
    )

    return render_template(
        "ch2.html",
        participant_id=participant_id
    )


@app.route(
    "/api/ch2/webhook",
    methods=["POST"]
)
def ch2_webhook():
    data = request.get_json(
        silent=True
    )

    if not data:
        return jsonify({
            "status": "error",
            "message": "JSON 형식이어야 합니다."
        }), 400

    webhook_url = data.get(
        "url",
        ""
    )

    if not isinstance(webhook_url, str):
        return jsonify({
            "status": "error",
            "message": "URL 형식이 올바르지 않습니다."
        }), 400

    webhook_url = webhook_url.strip()

    if webhook_url == "":
        return jsonify({
            "status": "error",
            "message": "URL을 입력하세요."
        }), 400

    command = (
        "/usr/bin/curl -v "
        "--connect-timeout 3 "
        "--max-time 10 "
        f"-X GET {webhook_url}"
    )

    print(
        f"[Challenge 2] 실행 명령: {command}",
        flush=True
    )

    try:
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            timeout=12
        )

        print(
            "[Challenge 2] 종료 코드: "
            f"{result.returncode}",
            flush=True
        )

        print(
            "[Challenge 2] stdout:\n"
            f"{result.stdout}",
            flush=True
        )

        print(
            "[Challenge 2] stderr:\n"
            f"{result.stderr}",
            flush=True
        )

        if result.returncode != 0:
            return jsonify({
                "status": "error",
                "message": "웹훅 전송에 실패했습니다.",
                "return_code": result.returncode,
                "detail": result.stderr
            }), 500

        return jsonify({
            "status": "success",
            "message": "웹훅 전송에 성공했습니다.",
            "return_code": result.returncode
        })

    except subprocess.TimeoutExpired:
        print(
            "[Challenge 2] 명령 실행 시간 초과",
            flush=True
        )

        return jsonify({
            "status": "error",
            "message": "웹훅 요청 시간이 초과됐습니다."
        }), 504

    except Exception as error:
        print(
            f"[Challenge 2] 오류: {error}",
            flush=True
        )

        return jsonify({
            "status": "error",
            "message": "요청 처리 중 오류가 발생했습니다.",
            "detail": str(error)
        }), 500


# ==========================================================
# Flask 실행 설정
# ==========================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8080,
        debug=False
    )
