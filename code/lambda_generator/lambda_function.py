import json
import os
import uuid
import boto3
from datetime import datetime

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
comprehend = boto3.client("comprehend")

BUCKET_NAME = os.environ["BUCKET_NAME"]
TABLE_NAME  = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)


def analyze_summary_tone(summary_text):
    """Uses Comprehend to flag a weak or negative professional summary."""
    try:
        result = comprehend.detect_sentiment(Text=summary_text[:5000], LanguageCode="en")
        sentiment = result["Sentiment"]
        scores = result["SentimentScore"]

        if sentiment == "NEGATIVE":
            tip = "Your summary reads negatively — consider rephrasing with more confident, achievement-focused language."
        elif sentiment == "NEUTRAL" and scores["Neutral"] > 0.85:
            tip = "Your summary is very neutral in tone — adding a few strong action verbs could make it stand out more."
        else:
            tip = "Your summary tone looks good."

        return {"sentiment": sentiment, "tip": tip}
    except Exception as e:
        # Comprehend is an enhancement, not critical path — the CV
        # still generates successfully even if this call fails.
        print(f"Comprehend sentiment check failed: {e}")
        return {"sentiment": "UNKNOWN", "tip": "Tone analysis unavailable."}


def build_cv_text(data):
    lines = []
    lines.append(data["full_name"].upper())
    lines.append(data["email"] + "  |  " + data["phone"])
    lines.append("")
    lines.append("=" * 60)
    lines.append("PROFESSIONAL SUMMARY")
    lines.append("=" * 60)
    lines.append(data["summary"])
    lines.append("")
    lines.append("=" * 60)
    lines.append("SKILLS")
    lines.append("=" * 60)
    lines.append(data["skills"])
    lines.append("")
    lines.append("=" * 60)
    lines.append("EXPERIENCE")
    lines.append("=" * 60)
    lines.append(data["experience"])
    lines.append("")
    lines.append("=" * 60)
    lines.append("EDUCATION")
    lines.append("=" * 60)
    lines.append(data["education"])
    return "\n".join(lines)


def lambda_handler(event, context):
    try:
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        required_fields = ["full_name","email","phone","summary","skills","experience","education"]
        missing = [f for f in required_fields if not body.get(f)]
        if missing:
            return _response(400, {"error": "Missing fields: " + ", ".join(missing)})

        cv_id   = str(uuid.uuid4())
        s3_key  = "cvs/" + cv_id + ".txt"
        cv_text = build_cv_text(body)

        s3.put_object(
            Bucket=BUCKET_NAME, Key=s3_key,
            Body=cv_text.encode("utf-8"), ContentType="text/plain",
        )

        download_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_key},
            ExpiresIn=3600,
        )

        tone_analysis = analyze_summary_tone(body["summary"])

        table.put_item(Item={
            "cv_id":      cv_id,
            "full_name":  body["full_name"],
            "email":      body["email"],
            "summary":    body["summary"],
            "skills":     body["skills"],
            "experience": body["experience"],
            "education":  body["education"],
            "s3_key":     s3_key,
            "sentiment":  tone_analysis["sentiment"],
            "created_at": datetime.utcnow().isoformat(),
        })

        return _response(200, {
            "cv_id":        cv_id,
            "download_url": download_url,
            "message":      "CV generated successfully",
            "tone_check":   tone_analysis["tip"],
        })

    except Exception as e:
        return _response(500, {"error": str(e)})


def _response(code, body):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body, ensure_ascii=False),
    }
