
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

CD flow looks for https://github.com/bcgov/bcregistry-sre/blob/3ef95fd20b1ff5d7039b63fc28b1d179331ccd9d/.github/actions/backend-deploy-job/files/cloudbuild.yaml#L119
run_* to generate jobs in cloud jobs.
