export interface BudgetStatus {
  budget_id: number;
  category_id: number;
  category: string;
  currency: string;
  budgeted: string;
  spent: string;
  remaining: string;
  ratio: number;
  is_override: boolean;
}

export interface Goal {
  id: number;
  name: string;
  target_amount: string;
  currency: string;
  target_date: string | null;
  monthly_contribution: string | null;
  priority: number;
  is_emergency_fund: boolean;
  is_active: boolean;
  saved: string;
  remaining: string;
  ratio: number;
  months_to_target: number | null;
  required_monthly: string | null;
}

export interface Rate {
  rate_date: string;
  buy: string;
  sell: string;
  source: string;
}

export interface Alert {
  id: number;
  kind: string;
  message: string;
  evidence: Record<string, unknown>;
  transaction_id: number | null;
  created_at: string;
  read_at: string | null;
}

export interface Dashboard {
  month: string;
  base_currency: string;
  income: string;
  expenses: string;
  net: string;
  expenses_by_currency: Record<string, string>;
  by_category: Record<string, string>;
  uncategorized_expenses: string;
  trend: { month: string; income: string; expenses: string }[];
  budgets: BudgetStatus[];
  goals: Goal[];
  fx: Rate | null;
  unread_alerts: number;
  pending_categorization: number;
}

export interface Preferences {
  base_currency: string;
  budget_alert_threshold: number;
  emergency_fund_months: number;
  unusual_spend_zscore: number;
  unusual_spend_min_samples: number;
  monthly_income: number | null;
  monthly_income_currency: string;
  investment_safety_buffer: number;
  telegram_alerts: boolean;
}
