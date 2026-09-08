import json
import os
import boto3

dynamodb = boto3.resource("dynamodb")
comprehend = boto3.client("comprehend")
TABLE_NAME = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)


def extract_key_phrases(text):
    """Uses Comprehend instead of regex — understands multi-word
    phrases as single concepts rather than splitting into tokens."""
    if not text.strip():
        return set()

    result = comprehend.detect_key_phrases(Text=text[:5000], LanguageCode="en")
    phrases = {kp["Text"].lower().strip() for kp in result["KeyPhrases"]}
    return phrases


def lambda_handler(event, context):
    try:
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        cv_id           = body.get("cv_id")
        job_description = body.get("job_description", "")

        if not cv_id or not job_description:
            return _response(400, {"error": "cv_id and job_description are required"})

        cv_item = table.get_item(Key={"cv_id": cv_id}).get("Item")
        if not cv_item:
            return _response(404, {"error": "CV not found"})

        cv_text = " ".join([
            cv_item.get("summary",""), cv_item.get("skills",""),
            cv_item.get("experience",""), cv_item.get("education",""),
        ])

        jd_phrases = extract_key_phrases(job_description)
        cv_phrases = extract_key_phrases(cv_text)

        # Exact-phrase matches, plus partial overlap where a JD phrase
        # appears as a substring inside a longer CV phrase (or vice versa)
        matched = set()
        for jd_p in jd_phrases:
            if jd_p in cv_phrases or any(jd_p in cv_p or cv_p in jd_p for cv_p in cv_phrases):
                matched.add(jd_p)

        missing = jd_phrases - matched
        score = round(len(matched) / len(jd_phrases) * 100) if jd_phrases else 0
        top_missing = sorted(missing, key=len, reverse=True)[:15]

        if score >= 75:
            suggestion = "Strong match! Your CV aligns well with this job."
        elif score >= 50:
            suggestion = "Moderate match. Add the missing phrases if you have relevant experience."
        else:
            suggestion = "Weak match. Review the job description and tailor your CV accordingly."

        table.update_item(
            Key={"cv_id": cv_id},
            UpdateExpression="SET last_match_score = :s",
            ExpressionAttributeValues={":s": score},
        )

        return _response(200, {
            "match_score":         score,
            "missing_phrases":     top_missing,
            "matched_phrases_count": len(matched),
            "total_jd_phrases":    len(jd_phrases),
            "suggestions":         suggestion,
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
