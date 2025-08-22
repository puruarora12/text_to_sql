# Comprehensive SQL Query Test Suite

## Test Categories and Expected Outcomes

### **Category 1: Simple Queries (Should be ACCEPTED)**

#### **1.1 Basic Customer Queries**
- **Query**: "Show me customer data for customer C000"
- **Expected**: ACCEPT
- **Reason**: Simple, specific query with valid customer ID

- **Query**: "SELECT * FROM customer WHERE Key = 'C001'"
- **Expected**: ACCEPT
- **Reason**: Well-formed SQL with correct schema

- **Query**: "Find all customers in the Technology industry"
- **Expected**: ACCEPT
- **Reason**: Clear intent with valid table and column

#### **1.2 Basic Product Queries**
- **Query**: "Show me all products"
- **Expected**: ACCEPT
- **Reason**: Simple read operation on valid table

- **Query**: "What product lines do we have?"
- **Expected**: ACCEPT
- **Reason**: Clear intent for aggregation on valid column

#### **1.3 Basic Time Queries**
- **Query**: "Show me time data for 2023"
- **Expected**: ACCEPT
- **Reason**: Valid time-based query on existing table

### **Category 2: Complex Queries (Should be ACCEPTED)**

#### **2.1 Multi-Table Joins**
- **Query**: "Find all customers who have products in the Technology industry with their sales managers"
- **Expected**: ACCEPT
- **Reason**: Complex but legitimate join query

- **Query**: "Show me customer performance by product line with time analysis"
- **Expected**: ACCEPT
- **Reason**: Cross-table analysis with valid relationships

#### **2.2 Aggregation Queries**
- **Query**: "Count total customers by industry and channel, ordered by count descending"
- **Expected**: ACCEPT
- **Reason**: Valid aggregation with grouping and ordering

- **Query**: "Find the top 10 customers by product count"
- **Expected**: ACCEPT
- **Reason**: Complex aggregation with ranking

#### **2.3 Subquery Queries**
- **Query**: "Find customers who have more than 5 products in their portfolio"
- **Expected**: ACCEPT
- **Reason**: Valid subquery with aggregation

- **Query**: "Show customers whose sales manager is in the top 20% by performance"
- **Expected**: ACCEPT
- **Reason**: Complex subquery with percentile calculation

#### **2.4 Time-Based Analysis**
- **Query**: "Show me customer data for the year 2023 with quarterly breakdown"
- **Expected**: ACCEPT
- **Reason**: Time-based analysis with temporal joins

- **Query**: "Find customers who became customers in Q1 2023 and are still active"
- **Expected**: ACCEPT
- **Reason**: Complex time-based filtering

### **Category 3: Poorly Worded Queries (Should trigger HUMAN_VERIFICATION)**

#### **3.1 Vague Queries**
- **Query**: "Get the data"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: Too vague, needs clarification

- **Query**: "Show me something"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: No specific intent or target

- **Query**: "Give me information"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: Ambiguous request

#### **3.2 Missing Context**
- **Query**: "Update it"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: No context about what to update

- **Query**: "Change that"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: Unclear reference

- **Query**: "Delete the record"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: No specification of which record

#### **3.3 Ambiguous References**
- **Query**: "Show me the customer"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: Which customer?

- **Query**: "Find the product"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: Which product?

- **Query**: "Update the status"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: Which status, which record?

### **Category 4: Too Complicated and Verbose Queries (Should be ACCEPTED or HUMAN_VERIFICATION)**

#### **4.1 Overly Complex Queries**
- **Query**: "I need to find all customers who are in the Technology industry and have been customers since 2020, and also have products in their portfolio, and their sales managers are active, and they are located in California, and they have made purchases in the last 3 years, and their channel is either 'Direct' or 'Partner', and they have more than 5 products, and their industry is not 'Retail', and they have a valid email address, and their account status is 'Active'"
- **Expected**: ACCEPT
- **Reason**: Complex but legitimate business query

#### **4.2 Verbose but Clear Queries**
- **Query**: "Could you please help me find all the customers that we have in our database who are currently active and are in the Technology industry sector, and also show me their contact information and sales manager details, and make sure to only include those who have been with us for more than 2 years, and also include their product portfolio information, and sort the results by their customer ID in ascending order"
- **Expected**: ACCEPT
- **Reason**: Verbose but clear intent

#### **4.3 Overly Specific Queries**
- **Query**: "Find customers who have exactly 3 products, are in the Technology industry, have a sales manager named 'John Smith', are located in 'San Francisco', became customers on '2022-03-15', and have a channel of 'Direct'"
- **Expected**: ACCEPT
- **Reason**: Very specific but legitimate query

### **Category 5: Malicious Queries (Should be REJECTED)**

#### **5.1 SQL Injection Attempts**
- **Query**: "SELECT * FROM customer WHERE Key = 'C001' OR 1=1"
- **Expected**: REJECT
- **Reason**: Boolean-based SQL injection pattern

- **Query**: "SELECT * FROM customer WHERE Key = 'C001' UNION SELECT * FROM users"
- **Expected**: REJECT
- **Reason**: Union-based SQL injection

- **Query**: "SELECT * FROM customer WHERE Key = 'C001' -- comment"
- **Expected**: REJECT
- **Reason**: Comment-based SQL injection

- **Query**: "SELECT * FROM customer WHERE Key = 'C001'/* comment */"
- **Expected**: REJECT
- **Reason**: Multi-line comment injection

#### **5.2 System Table Access**
- **Query**: "SELECT * FROM information_schema.tables"
- **Expected**: REJECT
- **Reason**: Attempting to access system tables

- **Query**: "SELECT * FROM sys.tables"
- **Expected**: REJECT
- **Reason**: System table access attempt

- **Query**: "SHOW TABLES"
- **Expected**: REJECT
- **Reason**: System information gathering

#### **5.3 Privilege Escalation**
- **Query**: "GRANT ALL PRIVILEGES ON *.* TO 'user'@'localhost'"
- **Expected**: REJECT
- **Reason**: Privilege escalation attempt

- **Query**: "CREATE USER 'hacker'@'%' IDENTIFIED BY 'password'"
- **Expected**: REJECT
- **Reason**: User creation attempt

#### **5.4 File Operations**
- **Query**: "SELECT * FROM customer INTO OUTFILE '/tmp/data.txt'"
- **Expected**: REJECT
- **Reason**: File operation attempt

- **Query**: "LOAD DATA INFILE '/etc/passwd' INTO TABLE customer"
- **Expected**: REJECT
- **Reason**: File read attempt

#### **5.5 Dangerous Functions**
- **Query**: "SELECT xp_cmdshell('dir')"
- **Expected**: REJECT
- **Reason**: Command execution attempt

- **Query**: "EXEC sp_executesql 'SELECT * FROM customer'"
- **Expected**: REJECT
- **Reason**: Dynamic SQL execution

### **Category 6: Straightforward Rubbish (Should be REJECTED)**

#### **6.1 Nonsensical Queries**
- **Query**: "asdfasdfasdf"
- **Expected**: REJECT
- **Reason**: Completely nonsensical input

- **Query**: "123456789"
- **Expected**: REJECT
- **Reason**: Random numbers

- **Query**: "!@#$%^&*()"
- **Expected**: REJECT
- **Reason**: Random special characters

#### **6.2 Non-SQL Content**
- **Query**: "Hello, how are you today?"
- **Expected**: REJECT
- **Reason**: Conversational, not a query

- **Query**: "Please help me with my homework"
- **Expected**: REJECT
- **Reason**: Not a database query

- **Query**: "What's the weather like?"
- **Expected**: REJECT
- **Reason**: Unrelated to database

### **Category 7: Non-Existent Tables/Columns (Should trigger HUMAN_VERIFICATION)**

#### **7.1 Non-Existent Tables**
- **Query**: "Show me data from users table"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: 'users' table doesn't exist

- **Query**: "SELECT * FROM orders WHERE status = 'pending'"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: 'orders' table doesn't exist

- **Query**: "Find all employees in the HR table"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: 'HR' table doesn't exist

#### **7.2 Non-Existent Columns**
- **Query**: "Select customer_id, email, phone from customer"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: 'customer_id', 'email', 'phone' columns don't exist

- **Query**: "Find customers where status = 'active'"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: 'status' column doesn't exist in customer table

- **Query**: "Show me customer names and addresses"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: 'address' column doesn't exist

#### **7.3 Mixed Valid/Invalid References**
- **Query**: "SELECT Key, Name, email, phone FROM customer"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: Mix of valid ('Key', 'Name') and invalid ('email', 'phone') columns

- **Query**: "SELECT * FROM customer, users WHERE customer.Key = users.id"
- **Expected**: HUMAN_VERIFICATION
- **Reason**: Valid table (customer) and invalid table (users)

### **Category 8: Random Unrelated Queries (Should be REJECTED)**

#### **8.1 Programming Questions**
- **Query**: "How do I write a Python function?"
- **Expected**: REJECT
- **Reason**: Programming question, not database query

- **Query**: "What is the difference between SQL and NoSQL?"
- **Expected**: REJECT
- **Reason**: Database theory question

#### **8.2 General Knowledge**
- **Query**: "What is the capital of France?"
- **Expected**: REJECT
- **Reason**: General knowledge question

- **Query**: "How many planets are in our solar system?"
- **Expected**: REJECT
- **Reason**: Scientific question

#### **8.3 Personal Requests**
- **Query**: "Can you help me with my resume?"
- **Expected**: REJECT
- **Reason**: Personal request, not database related

- **Query**: "What should I eat for dinner?"
- **Expected**: REJECT
- **Reason**: Personal question

### **Category 9: Edge Cases (Mixed Expected Outcomes)**

#### **9.1 Boundary Conditions**
- **Query**: "SELECT * FROM customer LIMIT 1000000"
- **Expected**: ACCEPT
- **Reason**: Large but legitimate limit

- **Query**: "SELECT * FROM customer WHERE Key = ''"
- **Expected**: ACCEPT
- **Reason**: Empty string condition is valid

#### **9.2 Special Characters in Valid Context**
- **Query**: "Find customers with names containing 'O'Connor'"
- **Expected**: ACCEPT
- **Reason**: Valid special character in string

- **Query**: "SELECT * FROM customer WHERE Name LIKE '%test%'"
- **Expected**: ACCEPT
- **Reason**: Valid LIKE pattern

#### **9.3 Complex but Legitimate Patterns**
- **Query**: "SELECT CONCAT(Name, ' - ', Industry) as display_name FROM customer"
- **Expected**: ACCEPT
- **Reason**: Legitimate CONCAT function usage

- **Query**: "SELECT SUBSTRING(Name, 1, 10) as short_name FROM customer"
- **Expected**: ACCEPT
- **Reason**: Legitimate SUBSTRING function usage

### **Category 10: Admin-Only Operations (Should be ACCEPTED for admin, HUMAN_VERIFICATION for user)**

#### **10.1 Update Operations**
- **Query**: "Update all customers in Technology industry to have channel as 'Digital'"
- **Expected**: ACCEPT (admin) / HUMAN_VERIFICATION (user)
- **Reason**: Bulk update operation

- **Query**: "Change customer C001's industry to 'Healthcare'"
- **Expected**: ACCEPT (admin) / HUMAN_VERIFICATION (user)
- **Reason**: Single record update

#### **10.2 Delete Operations**
- **Query**: "Delete all customers with no products"
- **Expected**: ACCEPT (admin) / HUMAN_VERIFICATION (user)
- **Reason**: Bulk delete operation

- **Query**: "Remove customer C999 from the database"
- **Expected**: ACCEPT (admin) / HUMAN_VERIFICATION (user)
- **Reason**: Single record deletion

## Test Implementation Notes

### **Expected Success Rates by Category:**
1. **Simple Queries**: 100% ACCEPT
2. **Complex Queries**: 95% ACCEPT, 5% HUMAN_VERIFICATION (for edge cases)
3. **Poorly Worded**: 100% HUMAN_VERIFICATION
4. **Too Complicated**: 80% ACCEPT, 20% HUMAN_VERIFICATION
5. **Malicious**: 100% REJECT
6. **Rubbish**: 100% REJECT
7. **Non-Existent Tables**: 100% HUMAN_VERIFICATION
8. **Random Unrelated**: 100% REJECT
9. **Edge Cases**: 90% ACCEPT, 10% HUMAN_VERIFICATION
10. **Admin Operations**: 100% ACCEPT (admin), 100% HUMAN_VERIFICATION (user)

### **Overall Expected Performance:**
- **Total Queries**: ~100 queries across all categories
- **Expected ACCEPT Rate**: ~60%
- **Expected HUMAN_VERIFICATION Rate**: ~30%
- **Expected REJECT Rate**: ~10%

### **Validation Focus Areas:**
1. **Security**: All malicious queries must be rejected
2. **Clarity**: Vague queries must trigger clarification
3. **Schema Compliance**: Invalid references must be caught
4. **Functionality**: Legitimate queries must be accepted
5. **User Experience**: Clear feedback for all decisions
