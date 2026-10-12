from datetime import datetime
from jira import JIRA
import os
import sys
import requests

class JiraClient:
    def __init__(self, jira_config):
        print(f"[{datetime.now()}] [JIRA-DEBUG] __init__ started with config: {jira_config}")
        
        self.url = jira_config["url"]
        print(f"[{datetime.now()}] [JIRA-DEBUG] url set: {self.url}")
        
        self.username = jira_config["username"]
        print(f"[{datetime.now()}] [JIRA-DEBUG] username set: {self.username}")
        
        token_env = jira_config.get("token_env")
        print(f"[{datetime.now()}] [JIRA-DEBUG] token_env from config: {token_env}")
        if not token_env:
            raise ValueError("Missing 'token_env' in jira config")
        
        self.token = os.getenv(token_env)
        print(f"[{datetime.now()}] [JIRA-DEBUG] token from env '{token_env}': {'set' if self.token else 'MISSING/EMPTY'}")
        if not self.token:
            raise ValueError(f"Missing or empty env var '{token_env}' for Jira token")
        
        self.project_key = jira_config.get("project_key")
        print(f"[{datetime.now()}] [JIRA-DEBUG] project_key from config: {self.project_key}")
        if not self.project_key:
            raise ValueError("Missing 'project_key' in jira config (e.g., 'HORACE')")
        
        print(f"[{datetime.now()}] [JIRA-DEBUG] __init__ complete | Project: {self.project_key}")
        sys.stdout.flush()
        
        try:
            self.jira = JIRA(
                server=self.url,
                basic_auth=(self.username, self.token),
                options={'rest_api_version': '3', 'timeout': 10}
            )
            print(f"[{datetime.now()}] [JIRA] Client initialized for {self.url}")
            sys.stdout.flush()
        except Exception as e:
            import traceback
            print(f"[{datetime.now()}] [JIRA] Init error: {e}\n{traceback.format_exc()}")
            sys.stdout.flush()
            raise

    def get_issue(self, key):
        """Fetch a single Jira issue by key."""
        try:
            issue = self.jira.issue(key)
            return issue.raw  # Return raw dict for fields access
        except Exception as e:
            print(f"[{datetime.now()}] [JIRA] Get issue {key} failed: {e}")
            return None
    
    def get_pending_tickets(self, jql):
        """Get list of pending tickets (raw issues)."""
        try:
            print(f"[{datetime.now()}] [JIRA] Polling with JQL: {jql}")
            sys.stdout.flush()
            issues = self.jira.search_issues(jql, startAt=0, maxResults=5, fields=['key', 'summary', 'description', 'status', 'updated'])
            
            # === RELIABLE STATUS DEBUG ===
            status_code = "unknown"
            try:
                # The jira library stores the last response here
                if hasattr(self.jira, '_session') and hasattr(self.jira._session, 'last_response'):
                    status_code = self.jira._session.last_response.status_code
            except:
                pass
            total = getattr(issues, 'total', 0) if issues else 0
            print(f"[{datetime.now()}] [JIRA DEBUG] API response status: {status_code} | Total matching tickets: {total}")
            # === END STATUS DEBUG ===
            
            raw_issues = [issue.raw for issue in issues] if issues else []
            print(f"[{datetime.now()}] [JIRA] Found {len(raw_issues)} issue(s)")
            sys.stdout.flush()
            return raw_issues
        except Exception as e:
            import traceback
            print(f"[{datetime.now()}] [JIRA] Polling error: {e}\n{traceback.format_exc()}")
            sys.stdout.flush()
            return []

    def add_comment(self, issue_key, comment_text):
        """Add a comment (ADF body)."""
        try:
            adf_body = {
                "version": 1,
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment_text}]}]
            }
            self.jira.add_comment(issue_key, adf_body)
            print(f"[{datetime.now()}] [JIRA] Comment posted on {issue_key}")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] [JIRA] Comment skipped: {e}")
            return False

    def transition_issue(self, issue_key, status_name):
        """Transition issue to a new status."""
        try:
            self.jira.transition_issue(issue_key, status_name)
            print(f"[{datetime.now()}] [JIRA] Moved {issue_key} to {status_name}")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] [JIRA] Transition skipped: {e}")
            return False
			
    def create_mirror_ticket(self, summary, description, original_url, original_key, worker_prefix="", epic_key=None):
        """
        Create mirror ticket in output Jira as sub-task under Epic if provided.
        Handles both ADF dict and plain string description safely.
        """
        fields = {
            "project": {"key": self.project_key},
            "summary": f"[Mirror] {summary}",
            "issuetype": {"name": "Task"},
            "labels": [f"original-{original_key}", f"worker-{worker_prefix.lower()}"],
        }

        # Safe description handling (your existing logic)
        original_append = f"\n\nOriginal: {original_url} ({original_key})"
        if isinstance(description, dict) and 'content' in description:
            description = self.clean_adf_description(description)
            description.setdefault('content', []).append({
                "type": "paragraph",
                "content": [{"type": "text", "text": original_append}]
            })
            fields["description"] = description
        else:
            fields["description"] = str(description or "") + original_append

        # FIXED: Graceful handling if epic is in different project
        if epic_key:
            try:
                epic = self.jira.issue(epic_key)
                if epic and epic.fields.project.key == self.project_key:
                    fields["parent"] = {"key": epic_key}
                    print(f"[{datetime.now()}] [JIRA] Creating mirror as sub-task under Epic {epic_key}")
                else:
                    print(f"[{datetime.now()}] [JIRA] Epic {epic_key} is in different project → creating as normal Task")
            except Exception as e:
                print(f"[{datetime.now()}] [JIRA] Could not validate Epic {epic_key}: {e} → creating as normal Task")

        try:
            issue = self.jira.create_issue(fields=fields)
            mirror_key = issue.key
            print(f"[{datetime.now()}] [JIRA] Mirror ticket created: {mirror_key} as sub-task under Epic {epic_key or 'none'}")
            return mirror_key
        except Exception as e:
            print(f"[{datetime.now()}] [JIRA] Create mirror failed: {e}")
            raise

    def add_label(self, issue_key, label):
        """Add a label to an issue (used for mirrors)."""
        try:
            # Fetch current issue to get labels
            issue = self.jira.issue(issue_key)
            labels = issue.fields.labels or []
            if label not in labels:
                labels.append(label)
                # Use direct REST API for update to avoid library quirks
                url = f"{self.url}/rest/api/3/issue/{issue_key}"
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                auth = (self.username, self.token)
                payload = {"fields": {"labels": labels}}
                response = requests.put(url, json=payload, headers=headers, auth=auth)
                if response.status_code == 204:
                    print(f"[{datetime.now()}] [JIRA] Added label '{label}' to {issue_key} via REST")
                    return True
                else:
                    print(f"[{datetime.now()}] [JIRA] Label add failed (status {response.status_code}): {response.text}")
                    return False
            return False
        except Exception as e:
            print(f"[{datetime.now()}] [JIRA] Add label failed (continuing): {str(e)}")
            return False

    def get_processed_original_keys(self, jql):
        """Fetch recent mirrors and extract original keys from labels (with pagination)."""
        try:
            issues = []
            start_at = 0
            max_results = 50  # Batch size
            while True:
                batch = self.jira.search_issues(jql, startAt=start_at, maxResults=max_results, fields=['labels'])
                issues.extend(batch)
                if len(batch) < max_results:
                    break
                start_at += len(batch)

            original_keys = []
            for issue in issues:
                labels = issue.fields.labels or []
                for label in labels:
                    if label.startswith("original-"):
                        original_keys.append(label.replace("original-", ""))
            print(f"[{datetime.now()}] [JIRA] Found {len(original_keys)} processed original keys (from {len(issues)} issues)")
            return original_keys
        except Exception as e:
            print(f"[{datetime.now()}] [JIRA] Processed keys fetch skipped: {e}")
            return []
			
    def clean_adf_description(self, adf):
        """Recursively clean ADF to remove media/attachment nodes, replacing with placeholder text."""
        if not isinstance(adf, dict) or 'content' not in adf:
            return adf  # Not ADF or no content - return as is

        def clean_content(content_list):
            cleaned = []
            for node in content_list:
                if isinstance(node, dict):
                    node_type = node.get('type')
                    if node_type in ['media', 'mediaSingle', 'mediaInline', 'mediaGroup']:
                        # Replace with placeholder
                        placeholder = {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "[Attached file: Removed during mirror - see original ticket]"}]
                        }
                        cleaned.append(placeholder)
                    elif 'content' in node:
                        # Recurse nested
                        node['content'] = clean_content(node['content'])
                        cleaned.append(node)
                    else:
                        cleaned.append(node)
            return cleaned

        adf['content'] = clean_content(adf['content'])
        return adf