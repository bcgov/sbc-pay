
# Payment Related Jobs

The application runs a collection of tasks at definite intervals.

 Crond schduler is used with in the pod to ensure the tasks are run at scheduled frequencies.
 
 The different tasks are as below.
 


| Task Name             	| Description                                               	| Frequency  	| When If Exact time is required           	| Test and Dev CRON Expression 	| Prod CRON Expression 	|
|-----------------------	|-----------------------------------------------------------	|------------	|------------------------------------------	|------------------------------	|----------------------	|
| ACTIVATE_PAD_ACCOUNTS 	| Activate PAD accounts after confirmation Period           	| Daily Once 	| 12.01 AM . First minute start of the day 	|                              	|                      	|
| CREATE_CFS_ACCOUNTS   	|                                                           	|            	|                                          	|                              	|                      	|
| CREATE_INVOICES       	|                                                           	|            	|                                          	|                              	|                      	|
| GENERATE_STATEMENTS   	|                                                           	|            	|                                          	|                              	|                      	|
| SEND_NOTIFICATIONS    	|                                                           	|            	|                                          	|                              	|                      	|
| UPDATE_STALE_PAYMENTS 	| Finds stale payments and updates with latest PAYBC Status 	|            	|                                          	|                              	|                      	|
| UPDATE_GL_CODE        	|                                                           	|            	|                                          	|                              	|                      	|
|                       	|                                                           	|            	|                                          	|                              	|                      	|
|                       	|                                                           	|            	|                                          	|                              	|                      	|
|                       	|                                                           	|            	|                                          	|                              	|                      	|
|                       	|                                                           	|            	|                                          	|                              	|                      	|