import os
import boto3
from datetime import datetime, timedelta

aws_access_key_id=os.environ['aws_access_key_id']
aws_secret_access_key=os.environ['aws_secret_access_key']

def get_asg_instances(asg_name):
    ec2 = boto3.client('ec2',aws_access_key_id=aws_access_key_id,aws_secret_access_key=aws_secret_access_key,region_name='ap-south-1')
    asg = boto3.client('autoscaling',aws_access_key_id=aws_access_key_id,aws_secret_access_key=aws_secret_access_key,region_name='ap-south-1')
    
    # Get Auto Scaling Group details
    response = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
    if not response["AutoScalingGroups"]:
        return None
    
    asg_details = response["AutoScalingGroups"][0]

    # Get running instances in the Auto Scaling Group
    instance_ids = [instance["InstanceId"] for instance in asg_details["Instances"]]
    response = ec2.describe_instances(InstanceIds=instance_ids)
    instances = {}
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            instances[instance["InstanceId"]] = {
                "InstanceId": instance["InstanceId"],
                "SecurityGroups": instance["SecurityGroups"],
                "ImageId": instance["ImageId"],
                "VpcId": instance["VpcId"],
                "LaunchTime": instance["LaunchTime"],
                "AvailabilityZone": instance["Placement"]["AvailabilityZone"],
            }
    return instances

def verify_testcase_a(asg_name):
    asg_instances = get_asg_instances(asg_name)
    if not asg_instances:
        return False, "Auto Scaling Group not found or no running instances."

    # Verify if ASG desired count matches the running instances count
    asg = boto3.client('autoscaling',aws_access_key_id=aws_access_key_id,aws_secret_access_key=aws_secret_access_key,region_name='ap-south-1')
    response = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
    desired_count = response["AutoScalingGroups"][0]["DesiredCapacity"]

    if len(asg_instances) != desired_count:
        print(f"Failed - ASG Desired count: {desired_count}, Running Instances: {len(asg_instances)}")
    else:
        print("Passed - ASG Desired count matches Running Instances")

    # Verify if multiple instances are distributed across availability zones
    availability_zones = {instance["AvailabilityZone"] for instance in asg_instances.values()}
    if len(asg_instances) > 1 and len(availability_zones) < len(asg_instances):
        print("Failed - EC2 Instances are not distributed across multiple Availability Zones")
    else:
        print("Passed - EC2 Instances are available and distributed across multiple Availability Zones")

    # Verify SecurityGroups, ImageId, and VpcId on ASG running instances
    security_groups = {sg["GroupId"] for instance in asg_instances.values() for sg in instance["SecurityGroups"]}
    image_ids = {instance["ImageId"] for instance in asg_instances.values()}
    vpc_ids = {instance["VpcId"] for instance in asg_instances.values()}

    if len(security_groups) != 1 or len(image_ids) != 1 or len(vpc_ids) != 1:
        print("Failed - Security Group, Image ID, or VPC ID are not the same on all running instances")
    else:
        print("Passed - Security Group, Image ID, and VPC ID are the same on all running instances")

    # Find out uptime of ASG running instances and get the longest running instance.
    longest_running_instance = None
    longest_uptime = timedelta()

    for instance in asg_instances.values():
        instance_id = instance["InstanceId"]
        launch_time =   instance['LaunchTime']
        uptime = datetime.now(launch_time.tzinfo) - launch_time
        if uptime > longest_uptime:
            longest_uptime = uptime
            longest_running_instance = instance_id

    print(f"Longest Running Instance - ID: {longest_running_instance}, Uptime: {longest_uptime}")

def verify_testcase_b(asg_name):
    asg = boto3.client('autoscaling',aws_access_key_id=aws_access_key_id,aws_secret_access_key=aws_secret_access_key,region_name='ap-south-1')
    response = asg.describe_scheduled_actions(AutoScalingGroupName=asg_name)

    # Find the next scheduled action and calculate elapsed time
    if not response["ScheduledUpdateGroupActions"]:
        print("No Scheduled Actions found for the given ASG")
        return

    current_time = datetime.utcnow()
    scheduled_actions = response["ScheduledUpdateGroupActions"]
    next_scheduled_action = min(scheduled_actions, key=lambda x: x["StartTime"])
    start_time = next_scheduled_action["StartTime"].replace(tzinfo=None)
    elapsed_time = current_time - start_time
    hh_mm_ss = str(elapsed_time)
    print(f"Time to Next Scheduled Action - {hh_mm_ss}")

    # Calculate the total number of instances launched and terminated today
    launch_count = 0
    terminate_count = 0
    for action in scheduled_actions:
        if action["StartTime"].date() == current_time.date():
            if action["DesiredCapacity"] > action["MinSize"]:
                launch_count += action["DesiredCapacity"] - action["MinSize"]
            elif action["DesiredCapacity"] < action["MinSize"]:
                terminate_count += action["MinSize"] - action["DesiredCapacity"]

    print(f"Instances Launched Today - {launch_count}, Instances Terminated Today - {terminate_count}")


if __name__ == "__main__":
    asg_name = "lv-test-cpu"

    verify_testcase_a(asg_name)
    
    verify_testcase_b(asg_name)
