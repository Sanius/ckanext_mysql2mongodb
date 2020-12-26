from ckanext.mysql2mongodb.data_conv.schema_conversion import SchemaConversion
from ckanext.mysql2mongodb.data_conv.database_connection import ConvInitOption, ConvOutputOption
from ckanext.mysql2mongodb.data_conv.data_conversion import DataConversion
from ckanext.mysql2mongodb.data_conv.utilities import open_connection_mysql
# from schema_conversion import SchemaConversion
# from database_connection import ConvInitOption, ConvOutputOption
# from data_conversion import DataConversion
# from utilities import open_connection_mysql
import urllib, json, re, os, requests, time

def test(schema_name):
	"""
	Test conversion in development environment.
	"""
	try:
		print("Start conversion!")

		db_conf = read_database_config()
		package_conf = read_package_config()

		# schema_name = "Chinook"
		# schema_name = "classicmodels"
		# schema_name = "compose_key"
		# schema_name = "northwind"
		# schema_name = "sakila"
		# schema_name = "sportsdb_qa"
		# schema_name = "world"
		# schema_name = "world_x"
		# schema_name = "xtoss"
		# schema_name = "employees"
		# schema_name = "sample_ip"
		# schema_name = "sample_staff"

		mysql_host = db_conf["mysql_host"]
		mysql_username = db_conf["mysql_username"]
		mysql_password = db_conf["mysql_password"]
		mysql_port = db_conf["mysql_port"]
		mysql_dbname = schema_name
		
		os.system(f"mkdir -p ./blob_and_text_file/{schema_name}")
		os.system(f"mkdir -p ./conversion_log/{schema_name}")
		
		schema_conv_init_option = ConvInitOption(host = mysql_host, username = mysql_username, password = mysql_password, port = mysql_port, dbname = mysql_dbname)

		mongodb_host = db_conf["mongodb_host"]
		mongodb_username = db_conf["mongodb_username"]
		mongodb_password = db_conf["mongodb_password"]
		mongodb_port = db_conf["mongodb_port"]
		mongodb_dbname = schema_name
		schema_conv_output_option = ConvOutputOption(host = mongodb_host, username = mongodb_username, password = mongodb_password, port = mongodb_port, dbname = mongodb_dbname)

		schema_conversion = SchemaConversion()
		schema_conversion.set_config(schema_conv_init_option, schema_conv_output_option)
		schema_conversion.run()

		mysql2mongodb = DataConversion(schema_name)
		mysql2mongodb.set_config(schema_conv_init_option, schema_conv_output_option, schema_conversion)
		mysql2mongodb.run()

		print("Done!")
		return True

	except Exception as e:
		print(e)
		print("Convert fail!")


def convert_data(dataset_title, resource_id, sql_file_name, sql_file_url):
	"""
	Convert MySQL database to MongoDB in product environment (CKAN).
	Parameters:
		dataset_title: Name of dataset which resource was uploaded into
		resource_id: Id of uploaded resource
		sql_file_name: Name of uploaded resource
		sql_file_url: Downloaded path of resource
	Return: 
		True: Convert successfully
	"""
	try:
		package_conf = read_package_config()

		# Check if dataset is not the one which converted databases are upload to.
		if dataset_title != package_conf["package_id"]:
			print("CKAN starts converting!")
			if sql_file_name.split(".")[1] != "sql":
				print("Invalided MySQL backup file extension!")
				raise Exception()
			else:
				os.chdir("/srv/app/src/ckanext-mysql2mongodb/ckanext/mysql2mongodb/data_conv")
				os.system(f"mkdir -p ./downloads/{resource_id}")
				os.system(f"mkdir -p ./blob_and_text_file/{resource_id}")
				os.system(f"mkdir -p ./conversion_log/{resource_id}")
				os.system(f"curl -o ./downloads/{resource_id}/{sql_file_name} {sql_file_url}")

				db_conf = read_database_config()
				schema_name = sql_file_name.split(".")[0]

				mysql_host = db_conf["mysql_host"]
				mysql_username = db_conf["mysql_username"]
				mysql_password = db_conf["mysql_password"]
				mysql_port = db_conf["mysql_port"]
				mysql_dbname = schema_name
				
				mysql_conn = open_connection_mysql(mysql_host, mysql_username, mysql_password)
				mysql_cur = mysql_conn.cursor()
				mysql_cur.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_dbname};")
				mysql_cur.close()
				mysql_conn.close()

				os.system(f"mysql -h {mysql_host} -u {mysql_username} --password={mysql_password} {schema_name} < ./downloads/{resource_id}/{sql_file_name}")
				
				schema_conv_init_option = ConvInitOption(host = mysql_host, username = mysql_username, password = mysql_password, port = mysql_port, dbname = mysql_dbname)

				mongodb_host = db_conf["mongodb_host"]
				mongodb_username = db_conf["mongodb_username"]
				mongodb_password = db_conf["mongodb_password"]
				mongodb_port = db_conf["mongodb_port"]
				mongodb_dbname = schema_name
				schema_conv_output_option = ConvOutputOption(host = mongodb_host, username = mongodb_username, password = mongodb_password, port = mongodb_port, dbname = mongodb_dbname)

				schema_conversion = SchemaConversion()
				schema_conversion.set_config(schema_conv_init_option, schema_conv_output_option)
				schema_conversion.run()

				mysql2mongodb = DataConversion(resource_id)
				mysql2mongodb.set_config(schema_conv_init_option, schema_conv_output_option, schema_conversion)
				mysql2mongodb.run()

				os.system(f"mkdir -p mongodump_files/{resource_id}")
				os.system(f"mongodump --username {mongodb_username} --password {mongodb_password} --host {mongodb_host} --port {mongodb_port} --authenticationDatabase admin --db {mongodb_dbname} -o mongodump_files/{resource_id}")
				os.system(f"mkdir -p uploads/{resource_id}")
				os.system(f"cp -r mongodump_files/{resource_id}/{schema_name} uploads/{resource_id}/{schema_name}")
				os.system(f"cp -r blob_and_text_file/{resource_id} uploads/{resource_id}/blob_and_text_file")
				os.system(f"cp -r conversion_log/{resource_id} uploads/{resource_id}/conversion_log")
				os.chdir(f"./uploads/{resource_id}")
				os.system(f"zip -r {schema_name}.zip *")

				response = requests.post('http://localhost:5000/api/action/resource_create',
			          data={"package_id":package_conf["package_id"], "name":f"{schema_name}-{resource_id}.zip"},
			          headers={"X-CKAN-API-Key": package_conf["X-CKAN-API-Key"]},
			          files={'upload': open(f"{schema_name}.zip", 'rb')})

				print(response.content)
				print("CKAN convert done!")
				return True

	except Exception as e:
		print(e)
		print("CKAN convert fail!")

def read_package_config(file_url = "package_config.txt"):
	"""
	Read package configuration file to get information of destination dataset which contain converted database files.
	Return:
		{
			package_id: Name of destination dataset which contain converted database files
			X-CKAN-API-Key: API-Key of account who has write privilege to destination dataset 
		}
	"""
	try:
		package_conf = {}
		with open(file_url, "r") as f:
			lines = f.readlines()
		config_string_list = ["package_id", "X-CKAN-API-Key"]
		for line in lines:
			for config_string in config_string_list:
				conf = parse_one_configuration(line, config_string)
				if conf is not None:
					package_conf[config_string] = conf
					break

		return package_conf

	except Exception as e:
		print(e)
		print("Failed while read package config!")


def read_database_config():
	"""
	Read MySQL and MongoDB database configurations which were set in docker-compose.yml.
	Return {
		mysql_host: Host name of MySQL database,
		mysql_port: Port number of MySQL database,
		mysql_username: Username of an user of MySQL database,
		mysql_password: Password of an user of MySQL database,
		mongodb_host: Host name of MongoDB database,
		mongodb_port: Port number of MongoDB database,
		mongodb_username: Username of an user of MongoDB database,
		mongodb_password: Password of an user of MongoDB database
	}
	"""
	try:
		db_conf = {}
		file_url = "database_config.txt"
		with open(file_url, "r") as f:
			lines = f.readlines()
		config_string_list = [
			"mysql_host", 
			"mysql_port",
			"mysql_password",
			"mysql_username",
			"mongodb_host",
			"mongodb_username",
			"mongodb_port",
			"mongodb_password"
			]
		for line in lines:
			for config_string in config_string_list:
				conf = parse_one_configuration(line, config_string)
				if conf is not None:
					db_conf[config_string] = conf
					break

		return db_conf
		
	except Exception as e:
		print(e)
		print("Failed while reading database config!")

def parse_one_configuration(line, config_string):
	looking_for_conf = re.search(f"^{config_string}", line.strip(), re.IGNORECASE)
	if looking_for_conf is not None:
		return re.split(r'[\s]+=[\s]+', line.strip())[1][1:-1]
	else:
		return None

if __name__ == '__main__':
	schema_name_list = [
	"Chinook",
	"classicmodels",
	"compose_key",
	"northwind",
	"sakila",
	"sportsdb_qa",
	"world",
	"world_x",
	"xtoss",
	# "employees",
	# "sample_ip",
	# "sample_staff",
	]
	for schema_name in schema_name_list:
		tic = time.time()
		test(schema_name)
		tac = time.time()
		time_taken=int(tac-tic)
		print(f"Overall time: {time_taken}s")