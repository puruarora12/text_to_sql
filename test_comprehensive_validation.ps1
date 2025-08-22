# Comprehensive SQL Query Validation Test Script
# This script tests the validation system with a wide range of query types

# Create sessions
Write-Host "Creating admin session..." -ForegroundColor Green
$adminResponse = Invoke-RestMethod -Uri "http://127.0.0.1:5000/v1/threads/sessions" -Method POST -Headers @{"Content-Type"="application/json"} -Body '{"session_name": "admin-comprehensive", "user_type": "admin"}'
$adminSessionId = $adminResponse.payload.session_id
Write-Host "Admin session ID: $adminSessionId" -ForegroundColor Yellow

Write-Host "Creating user session..." -ForegroundColor Green
$userResponse = Invoke-RestMethod -Uri "http://127.0.0.1:5000/v1/threads/sessions" -Method POST -Headers @{"Content-Type"="application/json"} -Body '{"session_name": "user-comprehensive", "user_type": "user"}'
$userSessionId = $userResponse.payload.session_id
Write-Host "User session ID: $userSessionId" -ForegroundColor Yellow

# Comprehensive test cases
$testCases = @(
    # Category 1: Simple Queries (Should be ACCEPTED)
    @{
        name = "1.1_Simple_Customer_Query"
        content = "Show me customer data for customer C000"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Simple Queries"
        description = "Simple, specific query with valid customer ID"
    },
    @{
        name = "1.2_Well_Formed_SQL"
        content = "SELECT * FROM customer WHERE Key = 'C001'"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Simple Queries"
        description = "Well-formed SQL with correct schema"
    },
    @{
        name = "1.3_Industry_Filter"
        content = "Find all customers in the Technology industry"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Simple Queries"
        description = "Clear intent with valid table and column"
    },
    @{
        name = "1.4_All_Products"
        content = "Show me all products"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Simple Queries"
        description = "Simple read operation on valid table"
    },
    @{
        name = "1.5_Product_Lines"
        content = "What product lines do we have?"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Simple Queries"
        description = "Clear intent for aggregation on valid column"
    },
    @{
        name = "1.6_Time_Data"
        content = "Show me time data for 2023"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Simple Queries"
        description = "Valid time-based query on existing table"
    },

    # Category 2: Complex Queries (Should be ACCEPTED)
    @{
        name = "2.1_Multi_Table_Join"
        content = "Find all customers who have products in the Technology industry with their sales managers"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Complex Queries"
        description = "Complex but legitimate join query"
    },
    @{
        name = "2.2_Cross_Table_Analysis"
        content = "Show me customer performance by product line with time analysis"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Complex Queries"
        description = "Cross-table analysis with valid relationships"
    },
    @{
        name = "2.3_Aggregation_Query"
        content = "Count total customers by industry and channel, ordered by count descending"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Complex Queries"
        description = "Valid aggregation with grouping and ordering"
    },
    @{
        name = "2.4_Top_Customers"
        content = "Find the top 10 customers by product count"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Complex Queries"
        description = "Complex aggregation with ranking"
    },
    @{
        name = "2.5_Subquery_Products"
        content = "Find customers who have more than 5 products in their portfolio"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Complex Queries"
        description = "Valid subquery with aggregation"
    },
    @{
        name = "2.6_Time_Based_Analysis"
        content = "Show me customer data for the year 2023 with quarterly breakdown"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Complex Queries"
        description = "Time-based analysis with temporal joins"
    },

    # Category 3: Poorly Worded Queries (Should trigger HUMAN_VERIFICATION)
    @{
        name = "3.1_Vague_Get_Data"
        content = "Get the data"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Poorly Worded"
        description = "Too vague, needs clarification"
    },
    @{
        name = "3.2_Vague_Show_Something"
        content = "Show me something"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Poorly Worded"
        description = "No specific intent or target"
    },
    @{
        name = "3.3_Vague_Give_Info"
        content = "Give me information"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Poorly Worded"
        description = "Ambiguous request"
    },
    @{
        name = "3.4_Missing_Context_Update"
        content = "Update it"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Poorly Worded"
        description = "No context about what to update"
    },
    @{
        name = "3.5_Missing_Context_Change"
        content = "Change that"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Poorly Worded"
        description = "Unclear reference"
    },
    @{
        name = "3.6_Ambiguous_Customer"
        content = "Show me the customer"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Poorly Worded"
        description = "Which customer?"
    },

    # Category 4: Too Complicated and Verbose Queries
    @{
        name = "4.1_Overly_Complex_Query"
        content = "I need to find all customers who are in the Technology industry and have been customers since 2020, and also have products in their portfolio, and their sales managers are active, and they are located in California, and they have made purchases in the last 3 years, and their channel is either 'Direct' or 'Partner', and they have more than 5 products, and their industry is not 'Retail', and they have a valid email address, and their account status is 'Active'"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Too Complicated"
        description = "Complex but legitimate business query"
    },
    @{
        name = "4.2_Verbose_But_Clear"
        content = "Could you please help me find all the customers that we have in our database who are currently active and are in the Technology industry sector, and also show me their contact information and sales manager details, and make sure to only include those who have been with us for more than 2 years, and also include their product portfolio information, and sort the results by their customer ID in ascending order"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Too Complicated"
        description = "Verbose but clear intent"
    },

    # Category 5: Malicious Queries (Should be REJECTED)
    @{
        name = "5.1_Boolean_Injection"
        content = "SELECT * FROM customer WHERE Key = 'C001' OR 1=1"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Malicious"
        description = "Boolean-based SQL injection pattern"
    },
    @{
        name = "5.2_Union_Injection"
        content = "SELECT * FROM customer WHERE Key = 'C001' UNION SELECT * FROM users"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Malicious"
        description = "Union-based SQL injection"
    },
    @{
        name = "5.3_Comment_Injection"
        content = "SELECT * FROM customer WHERE Key = 'C001' -- comment"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Malicious"
        description = "Comment-based SQL injection"
    },
    @{
        name = "5.4_System_Table_Access"
        content = "SELECT * FROM information_schema.tables"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Malicious"
        description = "Attempting to access system tables"
    },
    @{
        name = "5.5_Privilege_Escalation"
        content = "GRANT ALL PRIVILEGES ON *.* TO 'user'@'localhost'"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Malicious"
        description = "Privilege escalation attempt"
    },
    @{
        name = "5.6_File_Operation"
        content = "SELECT * FROM customer INTO OUTFILE '/tmp/data.txt'"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Malicious"
        description = "File operation attempt"
    },

    # Category 6: Straightforward Rubbish (Should be REJECTED)
    @{
        name = "6.1_Nonsensical_Input"
        content = "asdfasdfasdf"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Rubbish"
        description = "Completely nonsensical input"
    },
    @{
        name = "6.2_Random_Numbers"
        content = "123456789"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Rubbish"
        description = "Random numbers"
    },
    @{
        name = "6.3_Special_Characters"
        content = "!@#$%^&*()"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Rubbish"
        description = "Random special characters"
    },
    @{
        name = "6.4_Conversational"
        content = "Hello, how are you today?"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Rubbish"
        description = "Conversational, not a query"
    },
    @{
        name = "6.5_Programming_Question"
        content = "How do I write a Python function?"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Rubbish"
        description = "Programming question, not database query"
    },

    # Category 7: Non-Existent Tables/Columns (Should trigger HUMAN_VERIFICATION)
    @{
        name = "7.1_Non_Existent_Users_Table"
        content = "Show me data from users table"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Non-Existent Tables"
        description = "'users' table doesn't exist"
    },
    @{
        name = "7.2_Non_Existent_Orders_Table"
        content = "SELECT * FROM orders WHERE status = 'pending'"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Non-Existent Tables"
        description = "'orders' table doesn't exist"
    },
    @{
        name = "7.3_Non_Existent_Columns"
        content = "Select customer_id, email, phone from customer"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Non-Existent Tables"
        description = "'customer_id', 'email', 'phone' columns don't exist"
    },
    @{
        name = "7.4_Non_Existent_Status_Column"
        content = "Find customers where status = 'active'"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Non-Existent Tables"
        description = "'status' column doesn't exist in customer table"
    },
    @{
        name = "7.5_Mixed_Valid_Invalid"
        content = "SELECT Key, Name, email, phone FROM customer"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Non-Existent Tables"
        description = "Mix of valid ('Key', 'Name') and invalid ('email', 'phone') columns"
    },

    # Category 8: Random Unrelated Queries (Should be REJECTED)
    @{
        name = "8.1_General_Knowledge"
        content = "What is the capital of France?"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Random Unrelated"
        description = "General knowledge question"
    },
    @{
        name = "8.2_Scientific_Question"
        content = "How many planets are in our solar system?"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Random Unrelated"
        description = "Scientific question"
    },
    @{
        name = "8.3_Personal_Request"
        content = "Can you help me with my resume?"
        sessionId = $userSessionId
        expected_result = "reject"
        category = "Random Unrelated"
        description = "Personal request, not database related"
    },

    # Category 9: Edge Cases (Mixed Expected Outcomes)
    @{
        name = "9.1_Large_Limit"
        content = "SELECT * FROM customer LIMIT 1000000"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Edge Cases"
        description = "Large but legitimate limit"
    },
    @{
        name = "9.2_Empty_String_Condition"
        content = "SELECT * FROM customer WHERE Key = ''"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Edge Cases"
        description = "Empty string condition is valid"
    },
    @{
        name = "9.3_Special_Characters_Valid"
        content = "Find customers with names containing 'O'Connor'"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Edge Cases"
        description = "Valid special character in string"
    },
    @{
        name = "9.4_Legitimate_CONCAT"
        content = "SELECT CONCAT(Name, ' - ', Industry) as display_name FROM customer"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Edge Cases"
        description = "Legitimate CONCAT function usage"
    },
    @{
        name = "9.5_Legitimate_SUBSTRING"
        content = "SELECT SUBSTRING(Name, 1, 10) as short_name FROM customer"
        sessionId = $userSessionId
        expected_result = "accept"
        category = "Edge Cases"
        description = "Legitimate SUBSTRING function usage"
    },

    # Category 10: Admin-Only Operations
    @{
        name = "10.1_Admin_Update_Bulk"
        content = "Update all customers in Technology industry to have channel as 'Digital'"
        sessionId = $adminSessionId
        expected_result = "accept"
        category = "Admin Operations"
        description = "Bulk update operation - admin should accept"
    },
    @{
        name = "10.2_User_Update_Bulk"
        content = "Update all customers in Technology industry to have channel as 'Digital'"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Admin Operations"
        description = "Bulk update operation - user should trigger verification"
    },
    @{
        name = "10.3_Admin_Delete"
        content = "Delete all customers with no products"
        sessionId = $adminSessionId
        expected_result = "accept"
        category = "Admin Operations"
        description = "Bulk delete operation - admin should accept"
    },
    @{
        name = "10.4_User_Delete"
        content = "Delete all customers with no products"
        sessionId = $userSessionId
        expected_result = "human_verification"
        category = "Admin Operations"
        description = "Bulk delete operation - user should trigger verification"
    }
)

# Create results directory
$resultsDir = "comprehensive_validation_results"
if (!(Test-Path $resultsDir)) {
    New-Item -ItemType Directory -Path $resultsDir
}

# Initialize statistics
$stats = @{
    total = 0
    passed = 0
    failed = 0
    categories = @{}
}

# Test each case
foreach ($testCase in $testCases) {
    $stats.total++
    
    # Initialize category stats if not exists
    if (!$stats.categories.ContainsKey($testCase.category)) {
        $stats.categories[$testCase.category] = @{
            total = 0
            passed = 0
            failed = 0
        }
    }
    $stats.categories[$testCase.category].total++
    
    Write-Host "Testing: $($testCase.name)" -ForegroundColor Cyan
    Write-Host "  Category: $($testCase.category)" -ForegroundColor Gray
    Write-Host "  Query: $($testCase.content)" -ForegroundColor Gray
    Write-Host "  Expected: $($testCase.expected_result)" -ForegroundColor Yellow
    Write-Host "  Description: $($testCase.description)" -ForegroundColor Gray
    
    $body = @{
        session_id = $testCase.sessionId
        messages = @(
            @{
                role = "user"
                content = $testCase.content
            }
        )
    } | ConvertTo-Json -Depth 3
    
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:5000/v1/threads/conversation" -Method POST -Headers @{"Content-Type"="application/json"} -Body $body
        
        # Save response to file
        $response | ConvertTo-Json -Depth 10 | Out-File -FilePath "$resultsDir\$($testCase.name)_response.json" -Encoding UTF8
        
        # Analyze the response
        $decision = $response.payload.decision
        $feedback = $response.payload.feedback
        $validation_confidence = $response.payload.validation_confidence
        $type = $response.payload.type
        
        # Determine actual result
        $actual_result = if ($type -eq "human_verification") { "human_verification" } else { $decision }
        
        # Check if result matches expectation
        $status = if ($actual_result -eq $testCase.expected_result) { "✅ PASS" } else { "❌ FAIL" }
        $statusColor = if ($actual_result -eq $testCase.expected_result) { "Green" } else { "Red" }
        
        Write-Host "  -> Actual Result: $actual_result" -ForegroundColor $statusColor
        Write-Host "  -> Status: $status" -ForegroundColor $statusColor
        Write-Host "  -> Validation Result: $validation_confidence" -ForegroundColor $(if ($validation_confidence -eq 1.0) {"Green"} else {"Red"})
        
        # Update statistics
        if ($actual_result -eq $testCase.expected_result) {
            $stats.passed++
            $stats.categories[$testCase.category].passed++
        } else {
            $stats.failed++
            $stats.categories[$testCase.category].failed++
        }
        
        # Handle human verification responses
        if ($type -eq "human_verification") {
            Write-Host "  -> Human verification required" -ForegroundColor Yellow
            
            if ($response.payload.requires_clarification) {
                Write-Host "  -> Requires clarification" -ForegroundColor Magenta
                Write-Host "  -> Query Type: $($response.payload.query_type)" -ForegroundColor Cyan
                
                # Provide a clarification response
                $clarificationBody = @{
                    session_id = $testCase.sessionId
                    messages = @(
                        @{
                            role = "user"
                            content = "I want to see customer information with their product details and sales data"
                        }
                    )
                } | ConvertTo-Json -Depth 3
                
                $clarificationResponse = Invoke-RestMethod -Uri "http://127.0.0.1:5000/v1/threads/conversation" -Method POST -Headers @{"Content-Type"="application/json"} -Body $clarificationBody
                
                # Save clarification response
                $clarificationResponse | ConvertTo-Json -Depth 10 | Out-File -FilePath "$resultsDir\$($testCase.name)_clarification_response.json" -Encoding UTF8
                
                Write-Host "  -> After clarification: $($clarificationResponse.payload.decision)" -ForegroundColor $(if ($clarificationResponse.payload.decision -eq "accept") {"Green"} else {"Yellow"})
            } else {
                # Standard human verification (yes/no)
                Write-Host "  -> Standard verification" -ForegroundColor Cyan
                
                $yesBody = @{
                    session_id = $testCase.sessionId
                    messages = @(
                        @{
                            role = "user"
                            content = "yes"
                        }
                    )
                } | ConvertTo-Json -Depth 3
                
                $yesResponse = Invoke-RestMethod -Uri "http://127.0.0.1:5000/v1/threads/conversation" -Method POST -Headers @{"Content-Type"="application/json"} -Body $yesBody
                
                # Save yes response
                $yesResponse | ConvertTo-Json -Depth 10 | Out-File -FilePath "$resultsDir\$($testCase.name)_yes_response.json" -Encoding UTF8
                
                Write-Host "  -> After 'yes': $($yesResponse.payload.decision)" -ForegroundColor $(if ($yesResponse.payload.decision -eq "executed_after_verification") {"Green"} else {"Yellow"})
            }
        }
        
    } catch {
        Write-Host "  -> Error: $($_.Exception.Message)" -ForegroundColor Red
        $error | ConvertTo-Json -Depth 10 | Out-File -FilePath "$resultsDir\$($testCase.name)_error.json" -Encoding UTF8
        $stats.failed++
        $stats.categories[$testCase.category].failed++
    }
    
    Write-Host ""
}

# Print comprehensive statistics
Write-Host "=== COMPREHENSIVE VALIDATION TEST RESULTS ===" -ForegroundColor Green
Write-Host "Total Tests: $($stats.total)" -ForegroundColor White
Write-Host "Passed: $($stats.passed)" -ForegroundColor Green
Write-Host "Failed: $($stats.failed)" -ForegroundColor Red
Write-Host "Success Rate: $([math]::Round(($stats.passed / $stats.total) * 100, 2))%" -ForegroundColor Yellow

Write-Host "`n=== CATEGORY BREAKDOWN ===" -ForegroundColor Green
foreach ($category in $stats.categories.Keys) {
    $catStats = $stats.categories[$category]
    $successRate = if ($catStats.total -gt 0) { [math]::Round(($catStats.passed / $catStats.total) * 100, 2) } else { 0 }
    Write-Host "$category`: $($catStats.passed)/$($catStats.total) ($successRate%)" -ForegroundColor $(if ($successRate -ge 80) {"Green"} elseif ($successRate -ge 60) {"Yellow"} else {"Red"})
}

Write-Host "`nAll comprehensive validation tests completed. Results saved in $resultsDir directory." -ForegroundColor Green
