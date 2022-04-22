NAGIOS REQUIRED MACROS

    # "$HOSTNAME$" 
    # "$SERVICEDESC$" 
    # "$HOSTADDRESS$" 
    #  $HOSTSTATE$ 
    #  $HOSTSTATEID$ 
    #  $HOSTEVENTID$ 
    #  $HOSTPROBLEMID$ 
    #  $SERVICESTATE$ 
    #  $SERVICESTATEID$ 
    #  $LASTSERVICESTATE$ 
    #  $LASTSERVICESTATEID$ 
    #  $LASTSERVICEEVENTID$ 
    #  $LASTSERVICEPROBLEMID$ 
    #  $SERVICESTATETYPE$ 
    #  $SERVICEATTEMPT$ 
    #  $MAXSERVICEATTEMPTS$ 
    #  $SERVICEEVENTID$ 
    #  $SERVICEPROBLEMID$ 
    #  "$SERVICEOUTPUT$" 
    #  "$LONGSERVICEOUTPUT$" 
    #  $SERVICEDOWNTIME$ 
    #  "$SERVICEACKCOMMENT$"  

NAGIOS COMMAND

--lastservicestateid="$LASTSERVICEPROBLEMID$" --servicestateid="$SERVICESTATEID$" --serviceeventid="$SERVICEPROBLEMID$" --serviceproblemid="$SERVICEEVENTID$" --lastserviceeventid="$LASTSEVICEEVENTID$" --lastserviceproblemid="$LASTSERVICEPROBLEMID$" --hostname="$HOSTNAME$" --type="Service" --summary="$SERVICEDESC$" --severity="INFO" --source="$HOSTNAME$" --component="MyComponent" --group="MyGroup" --class="MyClass" --customdetails="$SERVICEOUT$"



TESTS

CRITICAL STATE | INFO SEVERITY WITH DEBUG
--lastservicestateid="0" --servicestateid="2" --serviceeventid="0001" --serviceproblemid="0001" --lastserviceeventid="0000" --lastserviceproblemid="0000" --hostname="test-only" --type="Service" --summary="__test__info__pager_duty-handler__trigger__" --severity="INFO" --source="test-only" --component="MyComponent" --group="MyGroup" --class="MyClass" --customdetails="CRITICAL: This is only a test and is not actionable."
