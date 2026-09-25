<div align="center">

# 🧠 Design Concepts & Rationale

This file explains **why** each decision was made — focused on what's different in this AI-enhanced version.

![AWS](https://img.shields.io/badge/AWS-Free%20Tier-FF9900?style=flat-square&logo=amazonaws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Region](https://img.shields.io/badge/Region-eu--north--1-232F3E?style=flat-square)

</div>

---

### At a Glance

| Decision | Why |
|:---|:---|
| Replace regex matching entirely, not tune it | Regex can't understand multi-word phrases as one concept — no amount of tuning fixes that |
| Add sentiment analysis to the generator too | Two separate real gaps existed — matching accuracy and CV-writing quality — fixing one wouldn't fix the other |
| Rest of the architecture left untouched | Only the matching logic was the problem; changing unrelated parts risks new bugs for no benefit |
| Comprehend IAM scoped to `Resource: "*"` | Service limitation — no resource-level ARN support, same as SNS in an earlier project |
| EC2/ALB teardown discipline unchanged | Still the only hourly-billed resources in the stack |

### Contents

[![Why Comprehend](https://img.shields.io/badge/Why_Comprehend-30363D?style=flat-square)](#why)
[![Security Decisions](https://img.shields.io/badge/Security_Decisions-30363D?style=flat-square)](#security)
[![Cost Decisions](https://img.shields.io/badge/Cost_Decisions-30363D?style=flat-square)](#cost)

---

<a id="why"></a>
## 🤖 Why Comprehend, and Why Here

| Question | Answer |
|:---|:---|
| Why replace the regex matching instead of tuning it? | Regex fundamentally can't understand that "cloud security operations" is one concept — it can only ever compare individual tokens. No amount of tuning fixes that; the approach needed to change, not the parameters. |
| Why add sentiment analysis to the CV generator, not just fix the analyzer? | Both problems were real: the analyzer under-matched relevant CVs, and there was no feedback at all on how the CV's own writing came across. Fixing only the matching would have left the CV-quality gap untouched. |
| Why keep the rest of the architecture completely unchanged? | The original design (VPC, ALB, Lambda, API Gateway, S3, DynamoDB) wasn't the problem — only the matching logic was. Changing unrelated parts would risk introducing new bugs for no benefit, and would make it harder to isolate what actually improved. |
| Is Comprehend's key-phrase matching guaranteed to be more accurate than regex? | Not automatically — it understands phrases better, but it can also return generic phrases ("the candidate", "this position") that add noise. It's a better foundation, not a finished, tuned solution. |

---

<a id="security"></a>
## 🔐 Security Decisions

| Question | Answer |
|:---|:---|
| Why is the Comprehend IAM permission scoped to `Resource: "*"` when everything else uses exact ARNs? | Comprehend doesn't support resource-level permissions for `DetectSentiment` or `DetectKeyPhrases` — there's no bucket- or table-like resource to scope to. This is a constraint of the service itself, consistent with the same limitation documented for SNS in an earlier project. |
| Does adding Comprehend change the EC2/ALB/VPC security posture at all? | No — Comprehend is called entirely from inside the Lambda functions using the SDK, over AWS's internal network. It introduces no new inbound network exposure. |

---

<a id="cost"></a>
## 💰 Cost Decisions

| Question | Answer |
|:---|:---|
| Doesn't Comprehend have a free tier? | It has a free tier — 50,000 units/month — but only for the first 12 months of an AWS account's life under the legacy Free Tier model. This account was created after AWS's July 2025 switch to the credit-based Free Plan, which doesn't carry that specific per-service 12-month allowance. Every Comprehend call here draws from the account's signup credit. |
| If it's not free, why isn't cost a bigger concern here, unlike the WAF decision in another project? | Scale. Comprehend's standard APIs cost $0.0001 per 100-character unit with a 300-character minimum per call — a full test session of a few dozen calls costs a fraction of a cent. WAF's concern was a fixed hourly charge that accrues whether or not it's used; Comprehend only charges for what's actually called, which is negligible at demo volume. |
| Why keep the EC2/ALB teardown discipline from the original project unchanged? | Nothing about adding Comprehend changes the fact that EC2 and ALB are the only hourly-billed resources in this stack — the same reasoning from the original project still applies exactly as before. |
