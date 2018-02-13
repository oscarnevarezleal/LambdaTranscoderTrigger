"""
    Simple lambda trigger for firing off the elastic transcoder and cleaning up the
    source files after
"""

import json
import boto3

# Set all these variables when you upload (
bucket_name = 'assets.domain.com'  #change this
unconverted_prefix='media/'
converted_prefix='transcoded/transcoded_'
thumbnail_prefix='thumbnails/thumb_'
pipeline_id='1518536024542-y0dk99' #change this

# Semi-constant stuff
preset_id='1351620000001-100070' # This is System Preset:Web, basically MP4 max size 1280x720
region_name='us-east-1'
delete_upon_completion_enabled=True

# While a file shows up in the unconverted bucket, starts Elastic Transcoder
def start_et_handler(event, context):

    print ("Processing start handler")

    try:
        print (event.get('Records'))
        if (event!=None and 'Records' in event and
            len(event.get('Records'))==1 and
            's3' in event.get('Records')[0] and
            'object' in event.get('Records')[0].get('s3') and
            'key' in event.get('Records')[0].get('s3').get('object')):

            s3_object = event.get('Records')[0].get('s3').get('object')
            infile_key = s3_object.get('key')

            if (infile_key.startswith(unconverted_prefix)):
                outfile_key = converted_prefix+('.'.join(infile_key[len(unconverted_prefix):].split('.')[:-1]) + '.mp4')
                thumbnail_pattern = thumbnail_prefix+('.'.join(infile_key[len(unconverted_prefix):].split('.')[:-1]) + '-{count}')
                print("Starting processing on {0} to {1} thumbnail {2}", format(infile_key), format(outfile_key), format(thumbnail_pattern))
                start_transcode(infile_key,outfile_key,thumbnail_pattern)
                print("Started ok, subscribe to the SNS queue to find out when finished")
                return {'status' : 'ok'}
            else :
                return {'status' : 'ignored', 'message' : infile_key + ' has wrong path ' + unconverted_prefix}

        else :
            return {'status' : 'ignored', 'message':'Invalid input'}

    except Exception as exception:
        return {'status' : 'error',
                'message' : exception}

# This one deletes the source file when the target file shows up in the converted bucket
def delete_source_after_et_finished_handler(event, context):

    print ("Processing delete handler SNS:"+json.dumps(event))

    if delete_upon_completion_enabled:
        s3 = boto3.client('s3', region_name)

        try:
            if (event!=None and 'Records' in event and
                        len(event.get('Records'))==1 and
                    'Sns' in event.get('Records')[0] and
                    'Message' in event.get('Records')[0].get('Sns')) :
                message_string = event.get('Records')[0].get('Sns').get('Message')
                message = json.loads(message_string)
                state = message.get('state')
                source_key = message.get('input').get('key')

                if (source_key!=None and 'COMPLETED'==state):
                    s3.delete_object(
                        Bucket=bucket_name,
                        Key=source_key
                    )
                    return {'status' : 'ok', 'sourceKey' : source_key}
                else:
                    return {'status' : 'ignored', 'message' : 'no key or not a completed event'}
            else :
                return {'status' : 'ignored', 'message':'Invalid input'}
        except Exception as exception:
            return {'status' : 'error',
                    'message' : exception.message}
    else:
        return {'status' : 'ignored', 'message' : 'currently disabled'}

def start_transcode(in_file, out_file, thumbnail_pattern):
    """
    Submit a job to transcode a file by its filename. The
    built-in web system preset is used for the single output.
    """
    transcoder = boto3.client('elastictranscoder', region_name)
    transcoder.create_job(
            PipelineId=pipeline_id,
            Input={
                'Key': in_file,
                'FrameRate': 'auto',
                'Resolution': 'auto',
                'AspectRatio': 'auto',
                'Interlaced': 'auto',
                'Container': 'auto'
            },
            Outputs=[{
                'Key': out_file,
                'ThumbnailPattern': thumbnail_pattern,
                'PresetId': preset_id
            }]
)
