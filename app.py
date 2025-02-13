import re
import csv
import os
from flask import Flask, request, send_file, render_template
from werkzeug.utils import secure_filename
import tempfile
from datetime import datetime

# 导入之前的SQL转换逻辑
def extract_column_names(create_table_sql):
    fields_pattern = r'CREATE TABLE.*?\((.*?)\)[^)]*?;'
    fields_match = re.search(fields_pattern, create_table_sql, re.DOTALL)
    if not fields_match:
        return []
    
    fields_str = fields_match.group(1)
    column_pattern = r'`(\w+)`\s+(?:(?!PRIMARY|UNIQUE|KEY|INDEX|CONSTRAINT).)*?(?:,|$)'
    columns = re.findall(column_pattern, fields_str, re.DOTALL)
    return columns

def parse_insert_values(insert_sql):
    values_pattern = r'VALUES\s*\((.*?)\);'
    values_match = re.search(values_pattern, insert_sql, re.DOTALL)
    if not values_match:
        return []
    
    values_str = values_match.group(1)
    values = []
    current = ''
    in_quotes = False
    
    for char in values_str:
        if char == '\'' and not current.endswith('\\'):
            in_quotes = not in_quotes
            current += char
        elif char == ',' and not in_quotes:
            values.append(current.strip())
            current = ''
        else:
            current += char
    
    if current:
        values.append(current.strip())
    
    cleaned_values = []
    for value in values:
        value = value.strip()
        if value.lower() == 'null':
            cleaned_values.append(None)
        elif value == '':
            cleaned_values.append('')
        elif value.startswith("'") and value.endswith("'"):
            cleaned_values.append(value[1:-1])
        else:
            try:
                cleaned_values.append(int(value))
            except ValueError:
                try:
                    cleaned_values.append(float(value))
                except ValueError:
                    cleaned_values.append(value)
    
    return cleaned_values

def sql_to_csv(sql_content):
    create_table_pattern = r'CREATE TABLE[^;]+;'
    create_table_sql = re.search(create_table_pattern, sql_content).group(0)
    
    columns = extract_column_names(create_table_sql)
    
    insert_pattern = r'INSERT INTO[^;]+;'
    insert_statements = re.findall(insert_pattern, sql_content)
    
    # 使用临时文件
    temp_fd, temp_path = tempfile.mkstemp(suffix='.csv')
    with os.fdopen(temp_fd, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(columns)
        
        for insert_sql in insert_statements:
            values = parse_insert_values(insert_sql)
            if values:
                writer.writerow(values)
    
    return temp_path

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'sql_file' not in request.files:
            return render_template('index.html', error='No file uploaded')
        
        file = request.files['sql_file']
        if file.filename == '':
            return render_template('index.html', error='No file selected')
        
        if not file.filename.endswith('.sql'):
            return render_template('index.html', error='Please upload a .sql file')
        
        try:
            # 读取上传的SQL文件内容
            sql_content = file.read().decode('utf-8')
            
            # 转换为CSV
            csv_path = sql_to_csv(sql_content)
            
            # 生成下载文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            download_name = f'converted_{timestamp}.csv'
            
            # 返回CSV文件并在发送后删除临时文件
            return send_file(
                csv_path,
                mimetype='text/csv',
                as_attachment=True,
                download_name=download_name,
                max_age=0
            )
            
        except Exception as e:
            return render_template('index.html', error=f'Error during conversion: {str(e)}')
        
        finally:
            # 确保临时文件被删除
            if 'csv_path' in locals():
                try:
                    os.remove(csv_path)
                except:
                    pass
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)