<div align="center">

# 🛠️ Build Log — ATS CV Generator (AI-Enhanced)

Same build as the original ATS project, with Amazon Comprehend added to the two Lambda functions. Screenshots below are trimmed to states that prove something — a name or setting already shown in a table isn't repeated as an image.

![AWS](https://img.shields.io/badge/AWS-Free%20Tier-FF9900?style=flat-square&logo=amazonaws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Region](https://img.shields.io/badge/Region-eu--north--1-232F3E?style=flat-square)

</div>

---

### Contents
- 🏗️ [Core Infrastructure (Reused Pattern)](#core)
- 🔐 [IAM Role & Policy](#iam)
- ⚡ [Lambda — CV Generator + Comprehend](#lambda-generator)
- ⚡ [Lambda — JD Analyzer + Comprehend](#lambda-analyzer)
- 🔌 [API Gateway](#api-gateway)
- 🚀 [Flask Deployment](#flask)
- ✅ [End-to-End Test](#e2e-test)

---

<a id="core"></a>
## 🏗️ Core Infrastructure (Reused Pattern)

Identical pattern to the original ATS CV Generator project — same resource types, renamed with an `ats-ai-` prefix, deployed in `eu-north-1` instead of `us-east-1`.

| Resource | Value |
|:---|:---|
| Key pair | `ats-ai-keypair` |
| VPC | `ats-ai-vpc` — `10.0.0.0/16` |
| Subnets | `ats-ai-public-subnet-1` (eu-north-1a), `ats-ai-public-subnet-2` (eu-north-1b) |
| Internet Gateway | `ats-ai-igw` |
| Route Table | `ats-ai-public-rt` — `0.0.0.0/0 → igw` |
| Security Groups | `ats-ai-alb-sg` (HTTP from internet), `ats-ai-ec2-sg` (HTTP from ALB SG only) |
| EC2 | 2× `t3.micro`, one per subnet |
| Target Group + ALB | `ats-ai-target-group`, `ats-ai-alb` |
| S3 | `ats-ai-storage-<account-id>` |
| DynamoDB | `ats-ai-records` — partition key `cv_id` |

![Security groups](screenshots/06-sg-ec2.png)
![EC2 instances running](screenshots/07-ec2.png)
![Load balancer active](screenshots/08-alb.png)

> **Issue carried over from the original project:** `t2.micro` is not Free Tier–eligible on new AWS accounts (post-July 2025 Free Plan) — used `t3.micro`.

> **New issue — region-specific IP range:** EC2 Instance Connect's service IP range differs per region. The `us-east-1` range used in the original project (`18.206.107.24/29`) doesn't work here. The `eu-north-1` range is `13.48.4.200/30` — allowed on the SSH rule in `ats-ai-ec2-sg` instead.

---

<a id="iam"></a>
## 🔐 IAM Role & Policy

Adds Comprehend permissions to the same least-privilege pattern as the original project.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": ["s3:PutObject", "s3:GetObject"],
            "Resource": "arn:aws:s3:::ats-ai-storage-*/*"
        },
        {
            "Effect": "Allow",
            "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"],
            "Resource": "arn:aws:dynamodb:*:*:table/ats-ai-records"
        },
        {
            "Effect": "Allow",
            "Action": ["comprehend:DetectSentiment", "comprehend:DetectKeyPhrases"],
            "Resource": "*"
        }
    ]
}
```

> Comprehend doesn't support resource-level ARN scoping the way S3 and DynamoDB do — the wildcard `Resource: "*"` here is a limitation of the service, not a looser policy choice.

![IAM role with policy attached](screenshots/11-iam-role.png)

---

<a id="lambda-generator"></a>
## ⚡ Lambda — CV Generator + Comprehend

Builds the CV and saves it to S3, same as before — now also runs the professional summary through `DetectSentiment` and stores the result alongside the CV record.

| Setting | Value |
|:---|:---|
| Name | `ats-ai-cv-generator` |
| Runtime | Python 3.12 |
| Env vars | `BUCKET_NAME`, `TABLE_NAME` |
| Timeout / Memory | 30s / 256MB |

Full code: [`code/lambda_generator/lambda_function.py`](code/lambda_generator/lambda_function.py)

![Lambda generator configuration](screenshots/12-lambda-generator-config.png)

---

<a id="lambda-analyzer"></a>
## ⚡ Lambda — JD Analyzer + Comprehend

Replaces the original regex keyword extraction with `DetectKeyPhrases` on both the CV text and the job description, then compares the resulting phrase sets instead of individual words.

| Setting | Value |
|:---|:---|
| Name | `ats-ai-jd-analyzer` |
| Runtime | Python 3.12 |
| Env vars | `TABLE_NAME` |
| Timeout | 30s (Comprehend calls need more time than the old regex logic) |

Full code: [`code/lambda_analyzer/lambda_function.py`](code/lambda_analyzer/lambda_function.py)

![Lambda analyzer configuration](screenshots/13-lambda-analyzer-config.png)

---

<a id="api-gateway"></a>
## 🔌 API Gateway

Same two-endpoint structure as the original project.

| Setting | Value |
|:---|:---|
| API name | `ats-ai-api` (REST, Regional) |
| Resources | `/generate` → `ats-ai-cv-generator`, `/analyze` → `ats-ai-jd-analyzer` |
| Stage | `prod` |

![API Gateway invoke URL](screenshots/14-apigateway-invoke.png)

---

<a id="flask"></a>
## 🚀 Flask Deployment

Same Flask app and systemd setup as the original project, deployed to both EC2 instances via EC2 Instance Connect.

![Systemd service running](screenshots/15-systemd.png)

---

<a id="e2e-test"></a>
## ✅ End-to-End Test

Opened the ALB DNS name and generated a CV — the response includes a `tone_check` field from Comprehend sentiment analysis alongside the download link. Ran the JD analyzer with a real job description — key phrases matched as coherent multi-word concepts instead of fragmented single words.

| Check | Result |
|:---|:---:|
| CV generation + sentiment tone check | ✅ |
| JD analysis via key phrases | ✅ |
| Target group health | ✅ Healthy |

![CV generation with tone check](screenshots/16-fulltest-generate.png)
![JD analysis with key phrases](screenshots/16-fulltest-analyze.png)

> **Cleanup:** both EC2 instances terminated, ALB and target group deleted immediately after testing. Lambda, S3, DynamoDB, API Gateway left running (near-zero idle cost).
