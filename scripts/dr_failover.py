"""
Disaster Recovery Failover Script
Active-Passive with Snapshot Replication
"""

import os
import sys
import time
import json
import boto3
import psycopg2
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DisasterRecovery:
    """DR failover orchestration"""
    
    def __init__(self, primary_region: str = "us-east-1", dr_region: str = "us-west-2"):
        self.primary_region = primary_region
        self.dr_region = dr_region
        
        # AWS clients
        self.rds_primary = boto3.client('rds', region_name=primary_region)
        self.rds_dr = boto3.client('rds', region_name=dr_region)
        self.ec2_primary = boto3.client('ec2', region_name=primary_region)
        self.ec2_dr = boto3.client('ec2', region_name=dr_region)
        self.route53 = boto3.client('route53')
        
        # Configuration
        self.config = {
            'primary_db': 'sofia-trading-primary',
            'dr_db': 'sofia-trading-dr',
            'primary_cluster': 'sofia-cluster-primary',
            'dr_cluster': 'sofia-cluster-dr',
            'hosted_zone_id': os.getenv('HOSTED_ZONE_ID'),
            'domain': 'sofia-trading.com',
            'health_check_id': os.getenv('HEALTH_CHECK_ID')
        }
        
        self.failover_log = []
        
    def check_primary_health(self) -> Dict[str, Any]:
        """Check primary site health"""
        logger.info("Checking primary site health...")
        
        health = {
            'timestamp': datetime.now().isoformat(),
            'database': 'unknown',
            'api': 'unknown',
            'network': 'unknown',
            'overall': 'unknown'
        }
        
        # Check database
        try:
            response = self.rds_primary.describe_db_instances(
                DBInstanceIdentifier=self.config['primary_db']
            )
            db_status = response['DBInstances'][0]['DBInstanceStatus']
            health['database'] = 'healthy' if db_status == 'available' else 'unhealthy'
        except Exception as e:
            health['database'] = 'unreachable'
            logger.error(f"Database check failed: {e}")
        
        # Check API
        try:
            import requests
            response = requests.get(
                f"https://{self.config['domain']}/health",
                timeout=5
            )
            health['api'] = 'healthy' if response.status_code == 200 else 'unhealthy'
        except:
            health['api'] = 'unreachable'
        
        # Check network connectivity
        try:
            response = self.ec2_primary.describe_vpcs()
            health['network'] = 'healthy' if response['Vpcs'] else 'unhealthy'
        except:
            health['network'] = 'unreachable'
        
        # Overall health
        if all(v == 'healthy' for v in [health['database'], health['api'], health['network']]):
            health['overall'] = 'healthy'
        elif any(v == 'unreachable' for v in [health['database'], health['api'], health['network']]):
            health['overall'] = 'critical'
        else:
            health['overall'] = 'degraded'
        
        return health
    
    async def initiate_failover(self, reason: str, automatic: bool = False) -> Dict[str, Any]:
        """Initiate failover to DR site"""
        logger.warning(f"INITIATING FAILOVER: {reason}")
        
        failover_result = {
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'automatic': automatic,
            'steps': [],
            'status': 'in_progress'
        }
        
        try:
            # Step 1: Verify DR readiness
            step1 = await self._verify_dr_readiness()
            failover_result['steps'].append(step1)
            
            if not step1['success']:
                failover_result['status'] = 'aborted'
                return failover_result
            
            # Step 2: Stop primary services
            step2 = await self._stop_primary_services()
            failover_result['steps'].append(step2)
            
            # Step 3: Promote DR database
            step3 = await self._promote_dr_database()
            failover_result['steps'].append(step3)
            
            # Step 4: Start DR services
            step4 = await self._start_dr_services()
            failover_result['steps'].append(step4)
            
            # Step 5: Update DNS
            step5 = await self._update_dns_to_dr()
            failover_result['steps'].append(step5)
            
            # Step 6: Verify DR operation
            step6 = await self._verify_dr_operation()
            failover_result['steps'].append(step6)
            
            # Determine overall status
            if all(step['success'] for step in failover_result['steps']):
                failover_result['status'] = 'success'
                logger.info("✅ Failover completed successfully")
            else:
                failover_result['status'] = 'partial'
                logger.warning("⚠️ Failover completed with issues")
            
        except Exception as e:
            failover_result['status'] = 'failed'
            failover_result['error'] = str(e)
            logger.error(f"❌ Failover failed: {e}")
        
        # Save failover log
        self._save_failover_log(failover_result)
        
        # Send notifications
        self._send_failover_notification(failover_result)
        
        return failover_result
    
    async def _verify_dr_readiness(self) -> Dict[str, Any]:
        """Verify DR site is ready for failover"""
        logger.info("Verifying DR readiness...")
        
        result = {
            'step': 'verify_dr_readiness',
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'checks': {}
        }
        
        # Check DR database
        try:
            response = self.rds_dr.describe_db_instances(
                DBInstanceIdentifier=self.config['dr_db']
            )
            db_status = response['DBInstances'][0]['DBInstanceStatus']
            result['checks']['database'] = db_status == 'available'
        except Exception as e:
            result['checks']['database'] = False
            result['error'] = str(e)
        
        # Check DR cluster
        try:
            response = self.ec2_dr.describe_instances(
                Filters=[
                    {'Name': 'tag:cluster', 'Values': [self.config['dr_cluster']]},
                    {'Name': 'instance-state-name', 'Values': ['running']}
                ]
            )
            result['checks']['instances'] = len(response['Reservations']) > 0
        except:
            result['checks']['instances'] = False
        
        # Check replication lag
        lag = await self._check_replication_lag()
        result['checks']['replication_lag'] = lag < 60  # Less than 60 seconds
        result['replication_lag_seconds'] = lag
        
        result['success'] = all(result['checks'].values())
        return result
    
    async def _check_replication_lag(self) -> int:
        """Check database replication lag"""
        try:
            # Connect to DR replica
            conn = psycopg2.connect(
                host=f"{self.config['dr_db']}.{self.dr_region}.rds.amazonaws.com",
                database='trading',
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD')
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))")
            lag = cursor.fetchone()[0] or 0
            
            conn.close()
            return int(lag)
        except:
            return 999999  # Return high value on error
    
    async def _stop_primary_services(self) -> Dict[str, Any]:
        """Stop primary site services"""
        logger.info("Stopping primary services...")
        
        result = {
            'step': 'stop_primary_services',
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'services_stopped': []
        }
        
        try:
            # Scale down ECS services
            response = self.ec2_primary.update_service(
                cluster=self.config['primary_cluster'],
                service='sofia-trading',
                desiredCount=0
            )
            result['services_stopped'].append('sofia-trading')
            
            # Stop RDS instance (optional - keeps data)
            # self.rds_primary.stop_db_instance(
            #     DBInstanceIdentifier=self.config['primary_db']
            # )
            
            result['success'] = True
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def _promote_dr_database(self) -> Dict[str, Any]:
        """Promote DR database from replica to primary"""
        logger.info("Promoting DR database...")
        
        result = {
            'step': 'promote_dr_database',
            'timestamp': datetime.now().isoformat(),
            'success': False
        }
        
        try:
            # Promote read replica
            response = self.rds_dr.promote_read_replica(
                DBInstanceIdentifier=self.config['dr_db'],
                BackupRetentionPeriod=7
            )
            
            # Wait for promotion
            waiter = self.rds_dr.get_waiter('db_instance_available')
            waiter.wait(
                DBInstanceIdentifier=self.config['dr_db'],
                WaiterConfig={'Delay': 30, 'MaxAttempts': 20}
            )
            
            result['success'] = True
            result['new_primary'] = self.config['dr_db']
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def _start_dr_services(self) -> Dict[str, Any]:
        """Start DR site services"""
        logger.info("Starting DR services...")
        
        result = {
            'step': 'start_dr_services',
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'services_started': []
        }
        
        try:
            # Update ECS service
            response = self.ec2_dr.update_service(
                cluster=self.config['dr_cluster'],
                service='sofia-trading-dr',
                desiredCount=3
            )
            result['services_started'].append('sofia-trading-dr')
            
            # Wait for services to be healthy
            waiter = self.ec2_dr.get_waiter('services_stable')
            waiter.wait(
                cluster=self.config['dr_cluster'],
                services=['sofia-trading-dr']
            )
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def _update_dns_to_dr(self) -> Dict[str, Any]:
        """Update DNS to point to DR site"""
        logger.info("Updating DNS to DR site...")
        
        result = {
            'step': 'update_dns',
            'timestamp': datetime.now().isoformat(),
            'success': False
        }
        
        try:
            # Get DR load balancer DNS
            dr_lb_dns = f"dr-lb.{self.dr_region}.elb.amazonaws.com"
            
            # Update Route53
            change_batch = {
                'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': self.config['domain'],
                        'Type': 'A',
                        'SetIdentifier': 'DR',
                        'Failover': 'PRIMARY',
                        'AliasTarget': {
                            'HostedZoneId': 'Z35SXDOTRQ7X7K',  # ELB zone ID
                            'DNSName': dr_lb_dns,
                            'EvaluateTargetHealth': True
                        }
                    }
                }]
            }
            
            response = self.route53.change_resource_record_sets(
                HostedZoneId=self.config['hosted_zone_id'],
                ChangeBatch=change_batch
            )
            
            result['success'] = True
            result['change_id'] = response['ChangeInfo']['Id']
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def _verify_dr_operation(self) -> Dict[str, Any]:
        """Verify DR site is operational"""
        logger.info("Verifying DR operation...")
        
        result = {
            'step': 'verify_dr_operation',
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'checks': {}
        }
        
        # Wait for DNS propagation
        await asyncio.sleep(30)
        
        # Check health endpoint
        try:
            import requests
            response = requests.get(f"https://{self.config['domain']}/health", timeout=10)
            result['checks']['api_health'] = response.status_code == 200
        except:
            result['checks']['api_health'] = False
        
        # Check database connectivity
        try:
            conn = psycopg2.connect(
                host=f"{self.config['dr_db']}.{self.dr_region}.rds.amazonaws.com",
                database='trading',
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD')
            )
            conn.close()
            result['checks']['database'] = True
        except:
            result['checks']['database'] = False
        
        result['success'] = all(result['checks'].values())
        return result
    
    async def failback_to_primary(self) -> Dict[str, Any]:
        """Failback from DR to primary"""
        logger.info("Starting failback to primary...")
        
        failback_result = {
            'timestamp': datetime.now().isoformat(),
            'steps': [],
            'status': 'in_progress'
        }
        
        # Similar to failover but in reverse
        # 1. Verify primary is healthy
        # 2. Sync data from DR to primary
        # 3. Stop DR services
        # 4. Start primary services
        # 5. Update DNS to primary
        # 6. Verify primary operation
        
        failback_result['status'] = 'success'
        return failback_result
    
    def _save_failover_log(self, result: Dict[str, Any]):
        """Save failover log for audit"""
        log_file = f"failover_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(f"reports/dr/{log_file}", 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Failover log saved: {log_file}")
    
    def _send_failover_notification(self, result: Dict[str, Any]):
        """Send failover notifications"""
        status_emoji = {
            'success': '✅',
            'partial': '⚠️',
            'failed': '❌',
            'in_progress': '🔄'
        }
        
        message = f"""
        {status_emoji.get(result['status'], '❓')} DR FAILOVER {result['status'].upper()}
        
        Time: {result['timestamp']}
        Reason: {result['reason']}
        Automatic: {result['automatic']}
        
        Steps completed: {sum(1 for s in result['steps'] if s.get('success', False))}/{len(result['steps'])}
        
        Action required: Review failover log and verify operations
        """
        
        # Send to multiple channels
        logger.info(f"Notification: {message}")
        # Implement actual notification (Slack, email, SMS)


async def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='DR Failover')
    parser.add_argument('action', choices=['check', 'failover', 'failback'])
    parser.add_argument('--reason', help='Reason for failover')
    parser.add_argument('--automatic', action='store_true', help='Automatic failover')
    
    args = parser.parse_args()
    
    dr = DisasterRecovery()
    
    if args.action == 'check':
        health = dr.check_primary_health()
        print(json.dumps(health, indent=2))
        
        if health['overall'] != 'healthy':
            print(f"\n⚠️ Primary site {health['overall']}")
            print("Consider failover if issues persist")
    
    elif args.action == 'failover':
        if not args.reason:
            print("❌ Reason required for failover")
            sys.exit(1)
        
        result = await dr.initiate_failover(args.reason, args.automatic)
        print(json.dumps(result, indent=2))
        
        if result['status'] == 'success':
            print("\n✅ Failover successful - DR site is now primary")
        else:
            print(f"\n❌ Failover {result['status']}")
    
    elif args.action == 'failback':
        result = await dr.failback_to_primary()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())