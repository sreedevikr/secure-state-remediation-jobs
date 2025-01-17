# Copyright (c) 2020 VMware Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import json
import logging
import sys

import boto3

logging.basicConfig(level=logging.INFO)


class DefaultSecurityGroupRemoveRules(object):
    def parse(self, payload):
        """Parse payload received from Remediation Service.

        :param payload: JSON string containing parameters received from the remediation service.
        :type payload: str.
        :returns: Dictionary of parsed parameters
        :rtype: dict
        :raises: Exception, JSONDecodeError
        """
        remediation_entry = json.loads(payload)
        notification_info = remediation_entry.get("notificationInfo", None)
        finding_info = notification_info.get("FindingInfo", None)
        security_group_id = finding_info.get("ObjectId", None)

        object_chain = remediation_entry["notificationInfo"]["FindingInfo"][
            "ObjectChain"
        ]
        object_chain_dict = json.loads(object_chain)
        cloud_account_id = object_chain_dict["cloudAccountId"]
        region = finding_info.get("Region")

        logging.info(f"security_group_id: {security_group_id}")
        logging.info(f"region: {region}")
        logging.info(f"cloud_account_id: {cloud_account_id}")

        if security_group_id is None:
            raise Exception(
                "Missing parameters for 'payload.notificationInfo.ObjectId'."
            )

        return {
            "security_group_id": security_group_id,
            "region": region,
            "cloud_account_id": cloud_account_id,
        }

    def remediate(self, client, security_group_id, region, cloud_account_id):
        """Restrict all access for EC2 VPC default security group.
        :param client: Instance of the AWS boto3 client.
        :param security_group_id: The ID of the security group.
        :param region: Region in which the security group exists.
        :param cloud_account_id: AWS Account no.
        :type security_group_id: str.
        :type region: str.
        :type cloud_account_id: str.
        :returns: Integer signaling success or failure
        :rtype: int
        :raises: botocore.exceptions.ClientError
        """
        try:
            logging.info("    executing client.describe_security_group_rules")
            logging.info(f"    group-id: {security_group_id}")
            security_group_rules = client.describe_security_group_rules(
                Filters=[{"Name": "group-id", "Values": [security_group_id]},],
                MaxResults=1000,
            )
            for rule in security_group_rules["SecurityGroupRules"]:
                if rule["IsEgress"]:
                    logging.info("    executing client.revoke_security_group_egress")
                    logging.info(f"    GroupId: {security_group_id}")
                    logging.info(f"    SecurityGroupRuleIds: {rule['SecurityGroupRuleId']}")
                    client.revoke_security_group_egress(
                        GroupId=security_group_id,
                        SecurityGroupRuleIds=[rule["SecurityGroupRuleId"]]
                    )
                else:
                    logging.info("    executing client.revoke_security_group_ingress")
                    logging.info(f"    GroupId: {security_group_id}")
                    logging.info(f"    SecurityGroupRuleIds: {rule['SecurityGroupRuleId']}")
                    client.revoke_security_group_ingress(
                        GroupId=security_group_id,
                        SecurityGroupRuleIds=[rule["SecurityGroupRuleId"]]
                    )
            logging.info("successfully executed remediation")
        except Exception as e:
            logging.error(f"{str(e)}")

        return 0

    def run(self, args):
        """Run the remediation job.

        :param args: List of arguments provided to the job.
        :type args: list.
        :returns: int
        """
        params = self.parse(args[1])
        client = boto3.client("ec2", params["region"])
        logging.info("acquired ec2 client and parsed params - starting remediation")
        rc = self.remediate(client=client, **params)
        return rc


if __name__ == "__main__":
    logging.info("aws_ec2_default_security_group_traffic.py called - running now")
    obj = DefaultSecurityGroupRemoveRules()
    obj.run(sys.argv)
