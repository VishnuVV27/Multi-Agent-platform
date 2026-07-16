# Step 11: Rate Limiting & Budget Control

Production-grade request rate limiting, token management, and spending controls.

## 🎯 What's Implemented

### **1. Rate Limiter (Token Bucket Algorithm)**

Prevents request floods with configurable per-minute/hour limits.

```
Token Bucket Model:
├─ Requests per minute: 20 (free) → 500 (enterprise)
├─ Requests per hour: 500 (free) → 10,000 (enterprise)
└─ Token-based: Each request consumes 1 token
   Tokens refill based on time window
```

**Example:**
- Free user: 20 requests/minute
- After 10 requests: 10 tokens remaining
- Wait 30 seconds → refill 10 tokens
- Can make 10 more requests

### **2. Budget Manager**

Controls spending with monthly budget limits.

```
Monthly Budget (USD):
├─ Free: $10/month
├─ Pro: $100/month
└─ Enterprise: Unlimited

Tracks:
├─ Daily token usage
├─ Monthly spending
├─ Per-workflow costs
└─ Alerts at 80% of budget
```

### **3. Policy Engine**

YAML-based configuration for easy management.

```yaml
users:
  free:
    requests_per_minute: 20
    monthly_budget: 10.0
  pro:
    requests_per_minute: 100
    monthly_budget: 100.0

agents:
  research_agent:
    max_tokens_per_workflow: 50000
    max_cost_per_call: 1.00

provider_quotas:
  anthropic:
    requests_per_minute: 5000
    tokens_per_minute: 100000
```

---

## 🔧 Components

### **RateLimiter** (`src/rate_limiting/rate_limiter.py`)

```python
class RateLimiter:
    check_rate_limit(identifier, limit_type)
    → (is_allowed, info_dict)
    
    get_remaining_quota(identifier)
    → {requests_per_minute, requests_per_hour}
    
    reset_limit(identifier)
    → True/False
```

**Storage:** Redis (fast, in-memory)

### **BudgetManager** (`src/rate_limiting/budget_manager.py`)

```python
class BudgetManager:
    check_budget(user_id, requested_cost, tier)
    → (is_allowed, info_dict)
    
    track_cost(user_id, workflow_id, cost)
    → True/False
    
    get_budget_status(user_id, tier)
    → {used, remaining, percentage}
    
    get_workflow_cost_estimate(model, tokens)
    → estimated_cost
```

**Storage:** Redis (monthly) + Cost Tracker

### **PolicyEngine** (`src/rate_limiting/policy_engine.py`)

```python
class PolicyEngine:
    get_user_policy(tier)
    → {requests_per_minute, monthly_budget, ...}
    
    get_agent_policy(agent_id)
    → {max_tokens, max_cost_per_call}
    
    get_provider_quota(provider)
    → {rpm, tpm}
    
    get_workflow_max_cost()
    → max_cost_float
```

**Configuration:** YAML file (`config/rate_limit_policies.yaml`)

---

## 📊 Tier Structure

| Feature | Free | Pro | Enterprise |
|---------|------|-----|-----------|
| Requests/min | 20 | 100 | 500 |
| Requests/hour | 500 | 2,000 | 10,000 |
| Monthly budget | $10 | $100 | Unlimited |
| Tokens/day | 100K | 1M | Unlimited |
| Workflows/day | 50 | 500 | Unlimited |

---

## 🔌 API Endpoints

```
GET  /api/rate-limiting/check/{user_id}
     → Remaining requests per minute/hour

GET  /api/rate-limiting/budget/{user_id}
     → Monthly budget status
     → {used, remaining, percentage_used}

POST /api/rate-limiting/reset/{user_id}
     → Reset rate limit (admin only)

GET  /api/rate-limiting/policies/users/{tier}
     → Get policy for tier

GET  /api/rate-limiting/policies/agents/{agent_id}
     → Get agent-specific policy

GET  /api/rate-limiting/estimate-cost
     → Estimate workflow cost before running

GET  /api/rate-limiting/summary
     → System status and configured limits
```

---

## 💰 How Budget Works

### **Example: Free Tier User**

```
Monthly budget: $10.00

Jan 1: Start month
       used: $0.00, remaining: $10.00 ✅

Jan 15: Run 5 workflows
        cost: $4.50
        used: $4.50, remaining: $5.50 ✅

Jan 20: Run 3 more workflows
        cost: $5.00
        used: $9.50, remaining: $0.50 ⚠️ (warning at 80%)

Jan 25: Try to run workflow (cost: $0.75)
        would_exceed: true
        BLOCKED ❌
        
        Message: "Monthly budget exceeded. 
                  $9.50 spent of $10.00. 
                  Need $0.75 more."

Feb 1: Budget resets
       used: $0.00, remaining: $10.00 ✅
```

---

## 🚦 How Rate Limiting Works

### **Example: 20 requests/minute (Free Tier)**

```
Minute 1:00-1:01 (60 seconds, 20 tokens)

1:00:00 - Request 1   → 19 tokens left
1:00:03 - Request 2   → 18 tokens left
...
1:00:54 - Request 20  → 0 tokens left
1:00:55 - Request 21  → BLOCKED ❌
          "Rate limit exceeded. 
           20 requests per minute allowed.
           Reset in 5 seconds."

1:01:00 - Minute boundary
          20 new tokens added
          Can make 20 more requests
```

---

## 📈 How It Integrates

### **Workflow Execution Flow**

```
1. User sends request
2. RateLimiter.check_rate_limit()
   → Is user within requests/min limit?
   ↓ (Yes)
3. BudgetManager.check_budget(estimated_cost)
   → Will this request exceed monthly budget?
   ↓ (Yes)
4. Proceed to execute workflow
5. After LLM calls:
   → BudgetManager.track_cost(actual_cost)
   → Update Redis budget counter
6. Return result
```

### **Cost Estimation**

Before running a workflow, estimate cost:

```bash
GET /api/rate-limiting/estimate-cost
    ?model=claude-3.5-sonnet
    &estimated_tokens=5000

Response:
{
  "model": "claude-3.5-sonnet",
  "estimated_tokens": 5000,
  "estimated_cost": 0.045,
  "currency": "USD"
}
```

Then check if budget allows it:

```bash
GET /api/rate-limiting/budget/user_123
    ?tier=free

Response:
{
  "used": 9.50,
  "remaining": 0.50,
  "monthly_budget": 10.0
}

# 0.50 < 0.045? NO → Can't run this workflow
```

---

## ⚙️ Configuration

### **User Tiers** (`config/rate_limit_policies.yaml`)

```yaml
users:
  free:
    requests_per_minute: 20
    requests_per_hour: 500
    monthly_budget: 10.0
    max_tokens_per_day: 100000
```

### **Agent Limits**

```yaml
agents:
  research_agent:
    max_tokens_per_workflow: 50000
    max_cost_per_call: 1.00
```

### **Provider Quotas**

```yaml
provider_quotas:
  anthropic:
    requests_per_minute: 5000
    tokens_per_minute: 100000
```

---

## 📊 What Gets Tracked

**Per Request:**
- User ID
- Request timestamp
- Request success/failure

**Per Workflow:**
- Total cost
- Total tokens
- Execution time
- Model used

**Monthly:**
- User spending (Redis)
- Budget vs actual
- Alerts when approaching limit

---

## 🔔 Alerts

Automatic warnings when:
- **80% of budget spent** → Warn user
- **75% of rate limit reached** → Warn user
- **Budget exceeded** → Block request

---

## 🧪 Testing Rate Limiting

### **1. Check Remaining Quota**

```bash
curl http://localhost:8000/api/rate-limiting/check/user_123

Response:
{
  "remaining": {
    "requests_per_minute": 15,
    "requests_per_hour": 450
  }
}
```

### **2. Check Budget Status**

```bash
curl http://localhost:8000/api/rate-limiting/budget/user_123?tier=free

Response:
{
  "monthly_budget": 10.0,
  "used": 4.50,
  "remaining": 5.50,
  "percentage_used": 45.0
}
```

### **3. Estimate Cost**

```bash
curl "http://localhost:8000/api/rate-limiting/estimate-cost?model=claude-3.5-sonnet&estimated_tokens=5000"

Response:
{
  "estimated_cost": 0.045
}
```

---

## 🔒 Security

**What's protected:**
- ✅ Rate limits (Redis tokens)
- ✅ Budget (Redis monthly counter)
- ✅ Cost tracking (cost_tracker)

**Enforcement points:**
1. Before LLM call → Check rate limit
2. Before execution → Check budget
3. After execution → Track cost

**Admin operations:**
- Reset limits (for customer support)
- Override budgets (for special cases)
- Update policies (hot reload from YAML)

---

## 🚀 Features

### **Currently Implemented**
- ✅ Token bucket rate limiting
- ✅ Monthly budget enforcement
- ✅ Per-user, per-agent policies
- ✅ Cost estimation
- ✅ Budget tracking
- ✅ YAML configuration
- ✅ API endpoints
- ✅ Redis storage

### **Future Enhancements**
- Hourly/daily budgets (not just monthly)
- Per-agent cost limits
- Team/organization budgets
- Usage analytics dashboard
- Automated alerts via email/Slack
- Budget reset scheduling

---

## 📋 Configuration Management

Edit `config/rate_limit_policies.yaml` to:
- Change rate limits
- Update monthly budgets
- Add new agent constraints
- Adjust provider quotas
- Configure alert thresholds

Changes take effect immediately (hot reload).

---

**Step 11 Complete!** Rate limiting and budget control fully integrated.

Every request is now rate-limited and budget-aware. Users can't accidentally spend more than their monthly budget.

Next: Step 12 (Dashboard & Workflow Visualization)
