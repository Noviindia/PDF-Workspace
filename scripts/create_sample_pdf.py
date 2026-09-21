import os
import sys

try:
    from fpdf import FPDF
except ImportError:
    print("Please install fpdf2: pip install fpdf2")
    sys.exit(1)

def create_sample_pdf(paths):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Page 1: Title page
    pdf.add_page()
    pdf.set_font("helvetica", "B", 24)
    pdf.cell(0, 50, "Student Records 2024-25", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("helvetica", "", 18)
    pdf.cell(0, 20, "Government High School", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("helvetica", "I", 14)
    pdf.cell(0, 20, "Total Students: 50", new_x="LMARGIN", new_y="NEXT", align="C")
    
    # Define a helper function to draw tables
    def draw_table(title, headers, data):
        pdf.add_page()
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)
        
        pdf.set_font("helvetica", "B", 10)
        # S.No | Name | Roll No | Father's Name | DOB | Phone | Gender
        col_widths = [12, 35, 20, 40, 25, 30, 20]
        line_height = 8
        
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], line_height, header, border=1, align="C")
        pdf.ln(line_height)
        
        pdf.set_font("helvetica", "", 10)
        for row in data:
            for i, item in enumerate(row):
                pdf.cell(col_widths[i], line_height, str(item), border=1)
            pdf.ln(line_height)
    
    headers = ["S.No", "Name", "Roll No", "Father's Name", "DOB", "Phone", "Gender"]
    
    # Pages 2-3: Class 10 Section A
    c10_secA = [
        [1, "Rahul Kumar", "1041", "Rajesh Kumar", "15/03/2009", "9876543210", "Male"],
        [2, "Amit Singh", "1042", "Suresh Singh", "22/07/2009", "9876543211", "Male"],
        [3, "Neha Kumari", "1043", "Ramesh Prasad", "08/11/2009", "9876543212", "Female"],
        [4, "Priya Sharma", "1044", "Dinesh Sharma", "14/02/2009", "9876543213", "Female"],
        [5, "Vikash Yadav", "1045", "Manoj Yadav", "03/06/2009", "9876543214", "Male"],
        [6, "Sunita Devi", "1046", "Mohan Lal", "19/09/2009", "9876543215", "Female"],
        [7, "Rajesh Patel", "1047", "Govind Patel", "28/01/2009", "9876543216", "Male"],
        [8, "Kavita Gupta", "1048", "Arun Gupta", "05/04/2009", "9876543217", "Female"],
        [9, "Deepak Verma", "1049", "Sanjay Verma", "11/08/2009", "9876543218", "Male"],
        [10, "Anita Rani", "1050", "Bhola Nath", "25/12/2009", "9876543219", "Female"],
        [11, "Mohit Tiwari", "1051", "Ram Tiwari", "07/10/2009", "9876543220", "Male"],
        [12, "Pooja Singh", "1052", "Hari Singh", "16/05/2009", "9876543221", "Female"]
    ]
    draw_table("Class 10 - Section A", headers, c10_secA[:10])
    draw_table("Class 10 - Section A (Contd.)", headers, c10_secA[10:])
    
    # Page 4: Class 10 Section B
    c10_secB = [
        [1, "Rahul Singh", "1055", "Mohan Singh", "10/01/2009", "9876543310", "Male"],
        [2, "Sunita Verma", "1056", "Raj Verma", "20/02/2009", "9876543311", "Female"],
        [3, "Arun Kumar", "1057", "Vijay Kumar", "12/03/2009", "9876543312", "Male"],
        [4, "Meena Devi", "1058", "Ravi Prasad", "04/04/2009", "9876543313", "Female"],
        [5, "Pankaj Mishra", "1059", "Om Mishra", "09/05/2009", "9876543314", "Male"],
        [6, "Ritu Sharma", "1060", "Lal Sharma", "14/06/2009", "9876543315", "Female"],
        [7, "Sanjay Gupta", "1061", "Ram Gupta", "19/07/2009", "9876543316", "Male"],
        [8, "Geeta Yadav", "1062", "Shyam Yadav", "24/08/2009", "9876543317", "Female"],
        [9, "Vivek Pal", "1063", "Dinesh Pal", "29/09/2009", "9876543318", "Male"],
        [10, "Sapna Kumari", "1064", "Hari Nath", "05/10/2009", "9876543319", "Female"]
    ]
    draw_table("Class 10 - Section B", headers, c10_secB)
    
    # Pages 5-6: Class 9 Section A
    c9_secA = [
        [1, "Rahul Sharma", "2031", "Sanjeev Sharma", "12/04/2010", "9876544210", "Male"],
        [2, "Nisha Gupta", "2032", "Pramod Gupta", "23/05/2010", "9876544211", "Female"],
        [3, "Anil Kumar", "2033", "Rakesh Kumar", "14/06/2010", "9876544212", "Male"],
        [4, "Preeti Devi", "2034", "Kamal Nath", "07/07/2010", "9876544213", "Female"],
        [5, "Suraj Singh", "2035", "Vikram Singh", "19/08/2010", "9876544214", "Male"],
        [6, "Jyoti Patel", "2036", "Harish Patel", "30/09/2010", "9876544215", "Female"],
        [7, "Vikas Verma", "2037", "Subhash Verma", "11/10/2010", "9876544216", "Male"],
        [8, "Sneha Rani", "2038", "Jagdish Prasad", "22/11/2010", "9876544217", "Female"],
        [9, "Rohit Yadav", "2039", "Kishore Yadav", "03/12/2010", "9876544218", "Male"],
        [10, "Kiran Kumari", "2040", "Ashok Kumar", "15/01/2011", "9876544219", "Female"],
        [11, "Tarun Sharma", "2041", "Manish Sharma", "26/02/2011", "9876544220", "Male"],
        [12, "Reena Singh", "2042", "Naveen Singh", "09/03/2011", "9876544221", "Female"]
    ]
    draw_table("Class 9 - Section A", headers, c9_secA[:10])
    draw_table("Class 9 - Section A (Contd.)", headers, c9_secA[10:])
    
    # Page 7: Class 9 Section B (10 students)
    c9_secB = [
        [1, "Raj Kumar", "2051", "Bipin Kumar", "10/01/2010", "9876545210", "Male"],
        [2, "Meera Devi", "2052", "Rajesh Nath", "15/02/2010", "9876545211", "Female"],
        [3, "Aman Singh", "2053", "Manoj Singh", "20/03/2010", "9876545212", "Male"],
        [4, "Roshni Gupta", "2054", "Sunil Gupta", "25/04/2010", "9876545213", "Female"],
        [5, "Sumit Yadav", "2055", "Pratap Yadav", "30/05/2010", "9876545214", "Male"],
        [6, "Asha Sharma", "2056", "Virendra Sharma", "04/07/2010", "9876545215", "Female"],
        [7, "Alok Patel", "2057", "Kailash Patel", "09/08/2010", "9876545216", "Male"],
        [8, "Pinky Verma", "2058", "Naresh Verma", "14/09/2010", "9876545217", "Female"],
        [9, "Sachin Tiwari", "2059", "Gopal Tiwari", "19/10/2010", "9876545218", "Male"],
        [10, "Rekha Kumari", "2060", "Dharam Pal", "24/11/2010", "9876545219", "Female"]
    ]
    draw_table("Class 9 - Section B", headers, c9_secB)
    
    # Page 8: Class 8 Section A (8 students)
    c8_secA = [
        [1, "Ravi Kumar", "3011", "Mahesh Kumar", "12/05/2011", "9876546210", "Male"],
        [2, "Seema Devi", "3012", "Suresh Nath", "18/06/2011", "9876546211", "Female"],
        [3, "Ajay Singh", "3013", "Rajendra Singh", "24/07/2011", "9876546212", "Male"],
        [4, "Mamta Gupta", "3014", "Krishna Gupta", "30/08/2011", "9876546213", "Female"],
        [5, "Nitin Yadav", "3015", "Bhagwan Yadav", "05/10/2011", "9876546214", "Male"],
        [6, "Usha Sharma", "3016", "Jitendra Sharma", "11/11/2011", "9876546215", "Female"],
        [7, "Vishal Patel", "3017", "Prakash Patel", "17/12/2011", "9876546216", "Male"],
        [8, "Poonam Verma", "3018", "Satish Verma", "23/01/2012", "9876546217", "Female"]
    ]
    draw_table("Class 8 - Section A", headers, c8_secA)
    
    # Page 9: Summary
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Summary", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, "Total Students by Class", new_x="LMARGIN", new_y="NEXT", align="L")
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(60, 8, "Class/Section", border=1)
    pdf.cell(40, 8, "Total Students", border=1)
    pdf.ln(8)
    
    pdf.set_font("helvetica", "", 10)
    pdf.cell(60, 8, "Class 10 - Section A", border=1)
    pdf.cell(40, 8, "12", border=1)
    pdf.ln(8)
    pdf.cell(60, 8, "Class 10 - Section B", border=1)
    pdf.cell(40, 8, "10", border=1)
    pdf.ln(8)
    pdf.cell(60, 8, "Class 9 - Section A", border=1)
    pdf.cell(40, 8, "12", border=1)
    pdf.ln(8)
    pdf.cell(60, 8, "Class 9 - Section B", border=1)
    pdf.cell(40, 8, "10", border=1)
    pdf.ln(8)
    pdf.cell(60, 8, "Class 8 - Section A", border=1)
    pdf.cell(40, 8, "8", border=1)
    pdf.ln(8)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(60, 8, "Total", border=1)
    pdf.cell(40, 8, "52", border=1)
    pdf.ln(15)
    
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, "Gender Distribution", new_x="LMARGIN", new_y="NEXT", align="L")
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(50, 8, "Gender", border=1)
    pdf.cell(50, 8, "Count", border=1)
    pdf.ln(8)
    
    pdf.set_font("helvetica", "", 10)
    pdf.cell(50, 8, "Male", border=1)
    pdf.cell(50, 8, "26", border=1)
    pdf.ln(8)
    pdf.cell(50, 8, "Female", border=1)
    pdf.cell(50, 8, "26", border=1)
    pdf.ln(8)
    
    # Add page numbers
    for i in range(1, pdf.page_no() + 1):
        pdf.page = i
        pdf.set_y(-15)
        pdf.set_font("helvetica", "I", 8)
        pdf.cell(0, 10, f"Page {i}", align="C")
        
    for path in paths:
        pdf.output(path)
        print(f"Generated: {path}")

if __name__ == "__main__":
    paths = [
        "assets/sample/sample_students.pdf",
        "tests/fixtures/sample_students.pdf"
    ]
    create_sample_pdf(paths)
