import boto3
from botocore.config import Config
from botocore.exceptions import ClientError #new



aws_config = Config(
    region_name='us-gov-west-1',
    signature_version='v4',
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }
)

ec2 = boto3.client('ec2', config = aws_config)

def check_if_parser_started() -> bool:

    response = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
    instance_state = response["Reservations"][0]["Instances"][0]["State"]
    print(response["Reservations"][0]["Instances"][0]["State"])
    if instance_state == 64 or instance_state == 80:
        '''64 : Stopping
           80 : Stopped'''
        return False
    else:
        return True



def start_parser_instance() -> None:
    if not check_if_parser_started():
        try:
            ec2.start_instances(InstanceIds=[INSTANCE_ID], DryRun=False)
        except ClientError as e:
            print(e)

print(f'Parser started: {check_if_parser_started}')
