import os
import json
import pandas as pd
from openai import OpenAI
import concurrent.futures
import time
from tqdm import tqdm
from prompt import SYSTEM_PROMPT_FINDINGS_CHINESE, SYSTEM_PROMPT_FINDINGS_ENGLISH
import argparse

# Define the root directory for the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Global list to store removed cases (if any)
removed_case_list = []

def extract_report_sections(result):
    """
    Extract different sections from the AI-generated report result.
    
    Args:
        result (str): The raw output from the AI model containing findings and conclusion sections
        
    Returns:
        dict: A dictionary containing:
            - cleaned_findings: Extracted findings section
            - cleaned_conclusion: Extracted conclusion section
            - findings_parts: Parsed subsections of findings (overview, disease-specific findings, etc.)
    """
    try:
        # Extract findings section
        findings_start = result.find("<findings>") + len("<findings>")
        findings_end = result.find("</findings>")
        conclusion_start = result.find("<conclusion>") + len("<conclusion>")
        conclusion_end = result.find("</conclusion>")
        
        cleaned_findings = result[findings_start:findings_end].strip()
        cleaned_conclusion = result[conclusion_start:conclusion_end].strip()
        
        # Further parse findings section into subsections
        findings_parts = {}
        
        # Extract overall findings summary (supports both English and Chinese)
        overview_start = cleaned_findings.find("Overall Findings Summary:")
        if overview_start == -1:
            overview_start = cleaned_findings.find("整体所见概要:")
        
        if overview_start != -1:
            # Find the next section to determine the end of overview
            next_section = cleaned_findings.find("Findings Corresponding to Each Disease:")
            if next_section == -1:
                next_section = cleaned_findings.find("各疾病对应所见:")
            
            if next_section != -1:
                if "Overall Findings Summary:" in cleaned_findings:
                    overview = cleaned_findings[overview_start + len("Overall Findings Summary:"):next_section].strip()
                else:
                    overview = cleaned_findings[overview_start + len("整体所见概要:"):next_section].strip()
                findings_parts['整体所见概要'] = overview
        
        # Extract disease-specific findings (supports both English and Chinese)
        diseases_start = cleaned_findings.find("Findings Corresponding to Each Disease:")
        if diseases_start == -1:
            diseases_start = cleaned_findings.find("各疾病对应所见:")
        
        if diseases_start != -1:
            if "Findings Corresponding to Each Disease:" in cleaned_findings:
                diseases_section = cleaned_findings[diseases_start + len("Findings Corresponding to Each Disease:"):].strip()
            else:
                diseases_section = cleaned_findings[diseases_start + len("各疾病对应所见:"):].strip()
            findings_parts['各疾病对应所见'] = diseases_section
        
        return {
            'cleaned_findings': cleaned_findings,
            'cleaned_conclusion': cleaned_conclusion,
            'findings_parts': findings_parts
        }
        
    except Exception as e:
        print(f"Error extracting report sections: {str(e)}")
        return {
            'cleaned_findings': '',
            'cleaned_conclusion': '',
            'findings_parts': {}
        }

def process_findings_stage(client, original_findings, language='english'):
    """
    Process the findings using the appropriate language-specific prompt.
    
    Args:
        client (OpenAI): The OpenAI client instance
        original_findings (str): The original findings text to be processed
        language (str): Language for processing ('chinese' or 'english')
        
    Returns:
        str: The processed findings from the AI model, or None if error occurs
    """
    # Select the appropriate system prompt based on language
    if language.lower() == 'chinese':
        system_prompt = SYSTEM_PROMPT_FINDINGS_CHINESE
    else:
        system_prompt = SYSTEM_PROMPT_FINDINGS_ENGLISH
    
    # Prepare messages for the AI model
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""
Findings: {original_findings}
"""}
    ]
    
    try:
        # Make API call to process the findings
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.6,  # Moderate creativity for medical text processing
            max_tokens=2048,  # Sufficient tokens for medical report processing
            stream=False
        )
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error in findings stage: {str(e)}")
        return None

def process_single_report(client, findings, conclusion, disease_type, language='english'):
    """
    Process a single medical report by combining findings and conclusion.
    
    Args:
        client (OpenAI): The OpenAI client instance
        findings (str): The original findings section
        conclusion (str): The original conclusion section
        disease_type (str): The disease type/label for this report
        language (str): Language for processing ('chinese' or 'english')
        
    Returns:
        str: The processed report result from the AI model
    """
    # Combine findings and conclusion for comprehensive processing
    input_text = f"检查所见: {findings}\n检查结论: {conclusion}"
    
    # Process through the findings stage
    findings_result = process_findings_stage(client, input_text, language)
    
    return findings_result

def clean_reports(json_path, language='english'):
    """
    Main function to clean and structure medical reports from a JSON file.
    
    Args:
        json_path (str): Path to the input JSON file containing medical reports
        language (str): Language for processing ('chinese' or 'english')
    """
    # Initialize OpenAI client with DeepSeek API
    client = OpenAI(
        api_key="put your api key here", 
        base_url="put your base url here"
    )
    
    # Load medical reports data from JSON file
    with open(json_path, 'r', encoding='utf-8') as f:
        reports = json.load(f)
    
    # Create output directory structure based on input filename
    json_filename = os.path.splitext(os.path.basename(json_path))[0]
    output_base_dir = f'{ROOT_DIR}/structure/cleaned_by_deepseekv3/{json_filename}'
    
    # Initialize list to store data for Excel export
    excel_data = []
    
    # Process reports concurrently for better performance
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        
        # Submit all processing tasks to the thread pool
        for report in reports:
            future = executor.submit(
                process_single_report,
                client,
                report['原_检查所见'],    # Original findings
                report['原_检查结论'],    # Original conclusion
                report['标签'],          # Disease label
                language
            )
            futures.append((future, report))
            
        # Process results with progress bar
        for future, report in tqdm(futures, desc="Processing medical reports", total=len(futures)):
            try:
                # Get the processing result
                findings_result = future.result()
                
                if findings_result:
                    # Extract structured sections from the AI result
                    extracted_data = extract_report_sections(findings_result)
                    cleaned_findings = extracted_data['cleaned_findings']
                    cleaned_conclusion = extracted_data['cleaned_conclusion']
                    findings_parts = extracted_data['findings_parts']
                    
                    # Save individual report as JSON file with comprehensive data
                    output_file = f'{output_base_dir}/json_result/{report["FID"]}.json'
                    os.makedirs(f'{output_base_dir}/json_result', exist_ok=True)
                    
                    # Create comprehensive report data structure
                    report_data = {
                        'FID': report["FID"],                           # File/Report ID
                        '检查时间': report['检查时间'],                    # Examination date
                        '性别': report['性别'],                          # Gender
                        '年龄': report['年龄'],                          # Age
                        '临床诊断': report['临床诊断'],                   # Clinical diagnosis
                        '检查项目': report['检查项目'],                   # Examination type
                        '原_检查所见': report['原_检查所见'],              # Original findings
                        '原_检查结论': report['原_检查结论'],              # Original conclusion
                        '清理后_检查所见': cleaned_findings,              # Cleaned findings
                        '清理后_检查结论': cleaned_conclusion,            # Cleaned conclusion
                        '整体所见概要': findings_parts.get('整体所见概要', ''),        # Overall findings summary
                        '各疾病对应所见': findings_parts.get('各疾病对应所见', ''),    # Disease-specific findings
                        '各模态对应所见': findings_parts.get('各模态对应所见', ''),    # Modality-specific findings
                        '模态详情': findings_parts.get('模态详情', {}),              # Modality details
                        '标签': report['标签'],                          # Disease label
                        'findings_stage_result': findings_result        # Raw AI processing result
                    }
                    
                    # Save individual JSON file
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(report_data, f, ensure_ascii=False, indent=2)
        
                    # Prepare data for Excel export (excluding raw AI result for readability)
                    excel_data.append({
                        'FID': report["FID"],
                        '检查时间': report['检查时间'],
                        '性别': report['性别'],
                        '年龄': report['年龄'],
                        '临床诊断': report['临床诊断'],
                        '检查项目': report['检查项目'],
                        '原_检查所见': report['原_检查所见'],
                        '原_检查结论': report['原_检查结论'],
                        '清理后_检查所见': cleaned_findings,
                        '清理后_检查结论': cleaned_conclusion,
                        '整体所见概要': findings_parts.get('整体所见概要', ''),
                        '标签': report['标签']
                    })
                    
            except Exception as e:
                print(f"Error processing report {report['FID']}: {str(e)}")
    
    # Export all processed data to Excel file
    if excel_data:
        df = pd.DataFrame(excel_data)
        os.makedirs(output_base_dir, exist_ok=True)
        excel_output_path = f'{output_base_dir}/cleaned_reports.xlsx'
        df.to_excel(excel_output_path, index=False)
        print(f"Excel file saved to: {excel_output_path}")

if __name__ == "__main__":
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description='Clean and structure medical reports using DeepSeek AI API'
    )
    parser.add_argument(
        '--json_path', 
        type=str, 
        required=True, 
        help='Path to the input JSON file containing medical reports'
    )
    parser.add_argument(
        '--language', 
        type=str, 
        default='english', 
        choices=['chinese', 'english'], 
        help='Language for processing (chinese or english). Default: english'
    )
    
    # Parse arguments and run the main function
    args = parser.parse_args()
    clean_reports(args.json_path, args.language)
