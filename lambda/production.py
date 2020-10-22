from app import Config, create_app

try:
   from flask_serverless import aws_invoke
except ImportError:
   pass

class ProductionConfig(Config):
   DEBUG=False

app = create_app()
app.config.from_object('production.ProductionConfig')

def lambda_handler(event, context):
   return aws_invoke(app,event,block_headers=False)

if __name__ == '__main__':
    app.run()
