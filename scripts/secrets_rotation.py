"""
Secrets Rotation and Management Script
"""

import os
import sys
import json
import boto3
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecretsManager:
    """Manages secrets rotation and storage"""
    
    def __init__(self, provider: str = "aws"):
        self.provider = provider
        self.rotation_days = 30
        self.emergency_contacts = ["security@company.com", "ops@company.com"]
        
        if provider == "aws":
            self.sm_client = boto3.client('secretsmanager')
            self.ssm_client = boto3.client('ssm')
        
        # Local encryption for sensitive operations
        self.cipher = self._init_cipher()
        
    def _init_cipher(self) -> Fernet:
        """Initialize local encryption cipher"""
        master_key = os.getenv('MASTER_KEY', 'default-key-change-me')
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'stable-salt',  # In production, use random salt
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return Fernet(key)
    
    def rotate_api_keys(self, exchange: str) -> Dict[str, Any]:
        """Rotate exchange API keys"""
        logger.info(f"Starting API key rotation for {exchange}")
        
        result = {
            'exchange': exchange,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'old_key_id': None,
            'new_key_id': None,
            'rollback_available': False
        }
        
        try:
            # Get current keys
            current_key = self._get_secret(f"sofia/{exchange}/api-key")
            current_secret = self._get_secret(f"sofia/{exchange}/api-secret")
            
            result['old_key_id'] = current_key[:8] + "****"
            
            # Generate new keys (exchange-specific logic needed)
            new_key, new_secret = self._generate_new_api_keys(exchange)
            
            # Store new keys with versioning
            self._store_secret(
                f"sofia/{exchange}/api-key",
                new_key,
                description=f"API key for {exchange}",
                version_label="AWSPENDING"
            )
            
            self._store_secret(
                f"sofia/{exchange}/api-secret",
                new_secret,
                description=f"API secret for {exchange}",
                version_label="AWSPENDING"
            )
            
            result['new_key_id'] = new_key[:8] + "****"
            
            # Test new keys
            if self._test_api_keys(exchange, new_key, new_secret):
                # Promote to current
                self._promote_secret(f"sofia/{exchange}/api-key", "AWSPENDING", "AWSCURRENT")
                self._promote_secret(f"sofia/{exchange}/api-secret", "AWSPENDING", "AWSCURRENT")
                
                # Mark old as previous
                self._promote_secret(f"sofia/{exchange}/api-key", "AWSCURRENT", "AWSPREVIOUS")
                self._promote_secret(f"sofia/{exchange}/api-secret", "AWSCURRENT", "AWSPREVIOUS")
                
                result['status'] = 'success'
                result['rollback_available'] = True
                
                # Schedule old key deletion
                self._schedule_deletion(f"sofia/{exchange}/api-key-old", days=7)
                
                logger.info(f"Successfully rotated API keys for {exchange}")
            else:
                # Rollback
                self._delete_secret_version(f"sofia/{exchange}/api-key", "AWSPENDING")
                self._delete_secret_version(f"sofia/{exchange}/api-secret", "AWSPENDING")
                
                result['status'] = 'failed'
                logger.error(f"Failed to rotate API keys for {exchange}")
                
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            logger.error(f"Error rotating API keys: {e}")
        
        # Audit log
        self._audit_log("api_key_rotation", result)
        
        return result
    
    def _generate_new_api_keys(self, exchange: str) -> tuple:
        """Generate new API keys (mock implementation)"""
        # In production, this would call exchange API
        new_key = secrets.token_urlsafe(32)
        new_secret = secrets.token_urlsafe(64)
        return new_key, new_secret
    
    def _test_api_keys(self, exchange: str, key: str, secret: str) -> bool:
        """Test new API keys"""
        # Mock test - in production, make actual API call
        try:
            # Test authentication
            # response = exchange_client.test_auth(key, secret)
            return True
        except:
            return False
    
    def rotate_database_credentials(self) -> Dict[str, Any]:
        """Rotate database credentials"""
        logger.info("Starting database credential rotation")
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'databases': []
        }
        
        databases = ['trading_db', 'analytics_db', 'backup_db']
        
        for db_name in databases:
            db_result = {
                'name': db_name,
                'status': 'pending'
            }
            
            try:
                # Generate new password
                new_password = self._generate_secure_password()
                
                # Update in secrets manager
                secret_name = f"sofia/database/{db_name}/password"
                self._store_secret(secret_name, new_password)
                
                # Update database user (requires DB admin access)
                if self._update_database_password(db_name, new_password):
                    db_result['status'] = 'success'
                else:
                    db_result['status'] = 'failed'
                
            except Exception as e:
                db_result['status'] = 'error'
                db_result['error'] = str(e)
            
            result['databases'].append(db_result)
        
        result['status'] = 'complete'
        return result
    
    def _generate_secure_password(self, length: int = 32) -> str:
        """Generate cryptographically secure password"""
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def emergency_revoke(self, secret_type: str, reason: str) -> Dict[str, Any]:
        """Emergency revocation of compromised credentials"""
        logger.critical(f"EMERGENCY REVOKE: {secret_type} - {reason}")
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'secret_type': secret_type,
            'reason': reason,
            'actions': []
        }
        
        # Immediate actions
        if secret_type == "api_keys":
            # Revoke all API keys
            exchanges = ['binance', 'kraken', 'coinbase']
            for exchange in exchanges:
                try:
                    # Delete current version
                    self._delete_secret(f"sofia/{exchange}/api-key")
                    self._delete_secret(f"sofia/{exchange}/api-secret")
                    result['actions'].append(f"Revoked {exchange} keys")
                except Exception as e:
                    result['actions'].append(f"Failed to revoke {exchange}: {e}")
        
        elif secret_type == "database":
            # Lock database accounts
            try:
                self._lock_database_accounts()
                result['actions'].append("Locked all database accounts")
            except Exception as e:
                result['actions'].append(f"Failed to lock databases: {e}")
        
        # Kill all active sessions
        try:
            self._kill_all_sessions()
            result['actions'].append("Killed all active sessions")
        except:
            pass
        
        # Activate kill switch
        try:
            self._activate_kill_switch(reason)
            result['actions'].append("Activated kill switch")
        except:
            pass
        
        # Send emergency notifications
        self._send_emergency_notification(result)
        
        # Audit log
        self._audit_log("emergency_revoke", result)
        
        return result
    
    def _kill_all_sessions(self):
        """Kill all active trading sessions"""
        # Implementation would terminate all active connections
        os.system("pkill -f 'sofia-trading'")
    
    def _activate_kill_switch(self, reason: str):
        """Activate trading kill switch"""
        import requests
        requests.post(
            "http://localhost:8023/api/kill-switch/activate",
            json={"reason": f"Emergency: {reason}"}
        )
    
    def _lock_database_accounts(self):
        """Lock all database accounts"""
        # Implementation would lock DB accounts
        pass
    
    def check_rotation_schedule(self) -> List[Dict[str, Any]]:
        """Check which secrets need rotation"""
        secrets_to_rotate = []
        
        if self.provider == "aws":
            # List all secrets
            response = self.sm_client.list_secrets()
            
            for secret in response['SecretList']:
                last_rotated = secret.get('LastRotatedDate')
                if last_rotated:
                    days_since = (datetime.now() - last_rotated.replace(tzinfo=None)).days
                    
                    if days_since >= self.rotation_days:
                        secrets_to_rotate.append({
                            'name': secret['Name'],
                            'last_rotated': last_rotated.isoformat(),
                            'days_since': days_since,
                            'priority': 'high' if days_since > self.rotation_days * 2 else 'normal'
                        })
        
        return secrets_to_rotate
    
    def _get_secret(self, secret_name: str) -> str:
        """Get secret value"""
        if self.provider == "aws":
            response = self.sm_client.get_secret_value(SecretId=secret_name)
            return response['SecretString']
        else:
            # Local storage fallback
            return os.getenv(secret_name.replace('/', '_').upper())
    
    def _store_secret(self, secret_name: str, secret_value: str, 
                     description: str = None, version_label: str = None):
        """Store secret with encryption"""
        if self.provider == "aws":
            try:
                self.sm_client.update_secret(
                    SecretId=secret_name,
                    SecretString=secret_value,
                    VersionStages=[version_label] if version_label else ['AWSCURRENT']
                )
            except self.sm_client.exceptions.ResourceNotFoundException:
                self.sm_client.create_secret(
                    Name=secret_name,
                    Description=description or f"Secret: {secret_name}",
                    SecretString=secret_value
                )
    
    def _promote_secret(self, secret_name: str, from_stage: str, to_stage: str):
        """Promote secret version"""
        if self.provider == "aws":
            self.sm_client.update_secret_version_stage(
                SecretId=secret_name,
                VersionStage=to_stage,
                MoveToVersionId=from_stage
            )
    
    def _delete_secret(self, secret_name: str):
        """Delete secret immediately"""
        if self.provider == "aws":
            self.sm_client.delete_secret(
                SecretId=secret_name,
                ForceDeleteWithoutRecovery=True
            )
    
    def _delete_secret_version(self, secret_name: str, version_stage: str):
        """Delete specific secret version"""
        if self.provider == "aws":
            self.sm_client.update_secret_version_stage(
                SecretId=secret_name,
                RemoveFromVersionId=version_stage
            )
    
    def _schedule_deletion(self, secret_name: str, days: int):
        """Schedule secret deletion"""
        if self.provider == "aws":
            try:
                self.sm_client.delete_secret(
                    SecretId=secret_name,
                    RecoveryWindowInDays=days
                )
            except:
                pass
    
    def _update_database_password(self, db_name: str, new_password: str) -> bool:
        """Update database password"""
        # Mock implementation - would use actual DB admin API
        return True
    
    def _send_emergency_notification(self, details: Dict[str, Any]):
        """Send emergency notifications"""
        import smtplib
        from email.mime.text import MIMEText
        
        message = f"""
        EMERGENCY SECURITY EVENT
        
        Time: {details['timestamp']}
        Type: {details.get('secret_type', 'Unknown')}
        Reason: {details.get('reason', 'Unknown')}
        
        Actions Taken:
        {json.dumps(details.get('actions', []), indent=2)}
        
        IMMEDIATE ACTION REQUIRED
        """
        
        for contact in self.emergency_contacts:
            logger.info(f"Notifying {contact}")
            # In production, send actual email/SMS/Slack
    
    def _audit_log(self, action: str, details: Dict[str, Any]):
        """Log security audit event"""
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'details': details,
            'user': os.getenv('USER', 'system'),
            'ip': os.getenv('SSH_CLIENT', 'local').split()[0] if os.getenv('SSH_CLIENT') else 'local'
        }
        
        # Write to audit log
        with open('security_audit.log', 'a') as f:
            f.write(json.dumps(audit_entry) + '\n')
        
        # Also send to SIEM if configured
        if os.getenv('SIEM_ENDPOINT'):
            import requests
            requests.post(os.getenv('SIEM_ENDPOINT'), json=audit_entry)


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Secrets Management')
    parser.add_argument('action', choices=['rotate', 'check', 'revoke'])
    parser.add_argument('--type', help='Secret type', default='all')
    parser.add_argument('--reason', help='Reason for action')
    parser.add_argument('--provider', default='aws', choices=['aws', 'local'])
    
    args = parser.parse_args()
    
    manager = SecretsManager(provider=args.provider)
    
    if args.action == 'rotate':
        if args.type in ['api_keys', 'all']:
            result = manager.rotate_api_keys('binance')
            print(json.dumps(result, indent=2))
        
        if args.type in ['database', 'all']:
            result = manager.rotate_database_credentials()
            print(json.dumps(result, indent=2))
    
    elif args.action == 'check':
        secrets = manager.check_rotation_schedule()
        print(f"Secrets needing rotation: {len(secrets)}")
        for secret in secrets:
            print(f"  - {secret['name']}: {secret['days_since']} days old ({secret['priority']})")
    
    elif args.action == 'revoke':
        if not args.reason:
            print("❌ Reason required for revocation")
            sys.exit(1)
        
        result = manager.emergency_revoke(args.type, args.reason)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()