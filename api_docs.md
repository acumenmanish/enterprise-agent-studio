Smart Schedule AI Agent --- Query API Documentation
===================================================

The **Smart Schedule AI Agent Query API** (ai\_agent\_query\_api.php) is
a server-to-server REST endpoint designed for the AI Agent
backend. It allows the agent to securely query and write back
scheduling/production data into tenant databases without exposing raw
database credentials.

1. Overview & Architecture
--------------------------

-   **Endpoint URL:** /ai\_agent\_query\_api.php

-   **Method:** POST

-   **Content-Type:** application/json

-   **Authentication:** Bearer \<api\_token\>

-   **Database Resolution:** Automatically resolves the caller\'s tenant
    > database based on validated claims inside the JWT token
    > (store\_id, fyear, agent\_tenant).

### Core Security & Isolation Principles

1.  **Zero Database Exposure:** The client only receives a Bearer token
    > and the API endpoint URL. Hostnames, DB names, usernames, and
    > passwords are strictly hidden.

2.  **Table & Column Whitelisting:** Queries can only access explicit
    > table aliases. Real table names are hidden. Only whitelisted
    > columns are returned or accepted.

3.  **Automatic Store Isolation:** Every query is unconditionally scoped
    > to the caller\'s store\_id (WHERE store\_id =
    > \<resolved\_store\_id\>).

4.  **Financial Year Pinned Context:** Financial data tables are
    > automatically locked to the active financial year (fyear)
    > specified or resolved from the token.

5.  **Session & Key Validation:** Tokens are verified against active
    > browser sessions or live API keys. Revoked sessions/keys instantly
    > invalidate query access.

2. Request Headers
------------------

  **Header**        **Value**               **Description**
  ----------------- ----------------------- ----------------------------------------------------------------
  Authorization     Bearer \<api\_token\>   RS256 signed JWT API token issued during SSO / token retrieval
  Content-Type      application/json        Request payload format
  Cache-Control     no-store, no-cache      Prevents token caching
  Referrer-Policy   no-referrer             Prevents token leakage

3. Supported Table Aliases Summary
----------------------------------

Clients must use **Aliases** when querying or inserting data. Direct
table names are not permitted.

  **Alias (table)**   **Underlying Table / View**   **Operations Permitted**   **Store Scoped?**   **Special Notes**
  ------------------- ----------------------------- -------------------------- ------------------- --------------------------------------------------------
  phd                 production\_holiday\_detail   SELECT                     Yes                 
  ph                  production\_holiday           SELECT                     Yes                 
  machine             erp\_machine                  SELECT                     Yes                 Column restricted
  operation           erp\_operation                SELECT                     Yes                 Column restricted
  order               order\_booking                SELECT                     Yes                 Column restricted; supports friendly status filter
  interval            operation\_interval           SELECT                     Yes                 Returns all columns
  job\_ops            job\_operations               SELECT                     Yes                 Column restricted
  maintenance         pre\_maintenance\_schedule    *None*                     **No**              **Disabled** (Refused due to missing store\_id column)
  schedule\_insert    smart\_schedule\_insert       SELECT                     Yes                 Returns all columns
  schedule            smart\_schedule\_new          SELECT                     Yes                 DB View; Column restricted
  store               store                         SELECT                     Yes                 Column restricted
  unit                production\_unit              SELECT                     Yes                 Column restricted
  production          production\_report            SELECT                     Yes                 Column restricted; Financial year date-pinned
  shift               shift\_production             SELECT                     Yes                 Column restricted; Financial year date-pinned
  holiday\_shift      holiday\_to\_shift            SELECT                     Yes                 Column restricted
  cycle\_schedule     production\_cycle\_schedule   SELECT, INSERT             Yes                 Read / Write enabled; Column restricted

4. API Actions & Endpoint Specification
---------------------------------------

### 4.1 select Action

Executes a filtered search against a whitelisted table alias.

#### Request Parameters

  **Field**   **Type**   **Required**   **Description**
  ----------- ---------- -------------- ---------------------------------------------------------------------
  action      string     **Yes**        Must be \"select\"
  table       string     **Yes**        The table alias (e.g., \"order\", \"machine\", \"cycle\_schedule\")
  filters     object     No             Key-value pairs of criteria (e.g., {\"status\": \"open\"})
  limit       integer    No             Max rows to return (Default: 200, Hard Cap: 200)
  offset      integer    No             Offset for pagination (Default: 0)

#### Friendly Filters & Date Controls

-   **Order Status Alias (table: \"order\"):**

    -   {\"status\": \"open\"} maps to job\_status = 0

    -   {\"status\": \"closed\"} or {\"status\": \"close\"} maps to
        > job\_status = 1

-   **Financial Year Filter (fyear):**

    -   Accepts \"YYYY-YY\" format (e.g., \"2026-27\"). Automatically
        > converted to a date range BETWEEN \'YYYY-04-01\' AND
        > \'YYYY+1-03-31\'.

#### Example Request (select)

{\
\"action\": \"select\",\
\"table\": \"order\",\
\"filters\": {\
\"status\": \"open\",\
\"fyear\": \"2026-27\"\
},\
\"limit\": 50,\
\"offset\": 0\
}

#### Example Response (select)

{\
\"status\": \"success\",\
\"table\": \"order\",\
\"limit\": 50,\
\"offset\": 0,\
\"count\": 2,\
\"total\": 145,\
\"has\_more\": true,\
\"data\": \[\
{\
\"order\_id\": \"1001\",\
\"store\_id\": \"10\",\
\"order\_no\": \"ORD-2026-001\",\
\"ord\_rec\_date\": \"2026-05-12\",\
\"job\_status\": \"0\"\
},\
{\
\"order\_id\": \"1002\",\
\"store\_id\": \"10\",\
\"order\_no\": \"ORD-2026-002\",\
\"ord\_rec\_date\": \"2026-05-14\",\
\"job\_status\": \"0\"\
}\
\]\
}

### 4.2 insert Action

Inserts single or multiple records into a whitelisted table.

**Note:** Insert access is currently enabled exclusively for the
**cycle\_schedule** alias (production\_cycle\_schedule table).

#### Payload Options

1.  **Single Row Insert:** data is a JSON Object.

2.  **Batch Insert:** data is an Array of JSON Objects.

#### Single Row Insert Example

**Request Payload:**

{\
\"action\": \"insert\",\
\"table\": \"cycle\_schedule\",\
\"data\": {\
\"wo\_id\": \"WO-8892\",\
\"package\": \"Offset Printing\",\
\"plant\_name\": \"Plant 1\",\
\"ops\_seq\": 1,\
\"operation\": \"Printing\",\
\"mkr\_hours\": 1.5,\
\"required\_hours\": 4.0,\
\"machine\_id\": 12,\
\"machine\": \"Heidelberg Speedmaster\",\
\"shift\": \"A\",\
\"start\_time\": \"2026-09-22 08:00:00\",\
\"finish\_time\": \"2026-09-22 13:30:00\",\
\"duration\": 5.5,\
\"status\": \"planned\"\
}\
}

**Success Response:**

{\
\"status\": \"success\",\
\"table\": \"cycle\_schedule\"\
}

#### Batch Insert Example

**Request Payload:**

{\
\"action\": \"insert\",\
\"table\": \"cycle\_schedule\",\
\"data\": \[\
{\
\"wo\_id\": \"WO-8892\",\
\"ops\_seq\": 1,\
\"operation\": \"Printing\",\
\"machine\_id\": 12,\
\"start\_time\": \"2026-09-22 08:00:00\",\
\"finish\_time\": \"2026-09-22 13:30:00\"\
},\
{\
\"wo\_id\": \"WO-8892\",\
\"ops\_seq\": 2,\
\"operation\": \"Cutting\",\
\"machine\_id\": 15,\
\"start\_time\": \"2026-09-22 14:00:00\",\
\"finish\_time\": \"2026-09-22 16:00:00\"\
}\
\]\
}

**Success Response:**

{\
\"status\": \"success\",\
\"table\": \"cycle\_schedule\",\
\"inserted\": 2,\
\"requested\": 2\
}

5. Detailed Table Schemas & Whitelisted Columns
-----------------------------------------------

Below is the complete detail of accessible columns per table alias for
SELECT queries and INSERT write operations.

### 5.1 cycle\_schedule (production\_cycle\_schedule)

-   **SELECT Columns:** id, tenant\_id, wo\_id, package, store\_id,
    > plant\_name, ops\_seq, operation, sheet\_req, balance\_load,
    > mkr\_hours, required\_hours, department, dept\_id, machine\_id,
    > machine, shift, start\_time, finish\_time, duration,
    > planned\_delivery\_date, ord\_delivery\_date, status, created\_by,
    > modified\_date

-   **INSERT Allowed Columns:** tenant\_id, wo\_id, package, store\_id,
    > plant\_name, ops\_seq, operation, sheet\_req, balance\_load,
    > mkr\_hours, required\_hours, department, dept\_id, machine\_id,
    > machine, shift, start\_time, finish\_time, duration,
    > planned\_delivery\_date, ord\_delivery\_date, status, created\_by,
    > modified\_date *(Note: Primary key id is auto-incremented and
    > omitted from insert whitelist)*.

### 5.2 order (order\_booking)

-   **SELECT Columns:** order\_id, store\_id, order\_no, ord\_pre\_no,
    > ord\_rec\_date, ord\_est\_no, ord\_type, ord\_client\_id,
    > ord\_cname, ord\_cadd, sales\_order\_id, ord\_product\_id,
    > ord\_pname, ord\_product\_type, ord\_industry\_type, ord\_qty,
    > proceed\_qty, tolerance\_qty, ups, ord\_del\_date, delfactdate,
    > job\_status, date, ord\_close\_date

### 5.3 machine (erp\_machine)

-   **SELECT Columns:** machine\_id, store\_id, machine\_name, unit\_id,
    > per\_day, per\_month, per\_year, time\_interval, package,
    > shift\_a, shift\_b, shift\_c, totalhrs, no\_month,
    > no\_days\_month, no\_hour\_day, hourly\_rate, total\_amt,
    > chk\_parameter, shift\_A\_from, shift\_A\_to, shift\_a\_status,
    > shift\_B\_from, shift\_B\_to, shift\_b\_status, shift\_C\_from,
    > shift\_C\_to, shift\_c\_status, financial\_year, speed\_low,
    > speed\_std, speed\_high, speed\_unit

### 5.4 operation (erp\_operation)

-   **SELECT Columns:** opt\_id, store\_id, opt\_group\_id, opt\_group,
    > default, machine\_id, ptgapp\_id, opt\_name, opt\_unit,
    > opt\_unitgroup, mc\_speed, based\_on, package, date\_added,
    > date\_modified

### 5.5 schedule (smart\_schedule\_new - View)

-   **SELECT Columns:** ssid, package, pro\_cost\_id, estimation\_no,
    > store\_id, operation, body\_sort, sort, sheet\_req, kg\_req,
    > mkr\_hours, run\_hours, tot\_hours, depart\_id, opt\_id,
    > machine\_id, machine, wo\_id, to\_datetime, schedule\_hrs,
    > date\_added, modified\_date, reset\_status, operation\_sort,
    > order\_sort, schedule\_sort, intervals, opt\_completed

### 5.6 production (production\_report)

-   **SELECT Columns:** report\_id, store\_id, customer\_id,
    > package\_type, package, department, machine, machine\_id, shift,
    > makeready\_hrs, production\_hrs, non\_pro\_hours, pro\_hours, CU,
    > OE, makeready, remarks, operator, manager, supervisor,
    > total\_production, total\_wastage, total\_production\_kg,
    > total\_wastage\_kg, date, prepared\_by, financial\_year

### 5.7 shift (shift\_production)

-   **SELECT Columns:** shift\_id, store\_id, report\_id, package\_type,
    > order\_sort, order\_no, job\_name, job\_narration, opt\_id,
    > mch\_id, production, production\_new, comm\_item\_type, units,
    > hours, from\_time, to\_time, first\_reel, in\_reel\_no,
    > out\_reel\_no, laminates\_reel\_no, prev\_qty\_mtr, prev\_qty\_kg,
    > laminates\_qty\_mtr, laminates\_qty\_mtr\_return,
    > laminates\_qty\_kg, laminates\_qty\_kg\_return\_gw,
    > laminates\_qty\_kg\_return\_tw, laminates\_qty\_kg\_return,
    > gross\_weight, core\_weight, net\_weight, wastage\_kg,
    > total\_weight, production\_mtr, wastage\_mtr, total\_mtr,
    > baby\_roll\_weight, baby\_roll\_count, mtr\_baby\_roll, mtc1,
    > mtc2, mtc3, matid1, matid2, matid3, detail, date, financial\_year,
    > mr\_hrs, prod\_hrs, wastage, wastage\_new, other\_name,
    > operation\_id, supervisor\_id, department\_manager\_id,
    > operator\_name, supervisor\_name, manager\_name,
    > qc\_check\_status, itemtype, mr\_hrs\_start, mr\_hrs\_end,
    > prod\_hrs\_start, prod\_hrs\_end, kg\_return, kg\_return\_gw,
    > kg\_return\_tw, mtr\_return, wosheet, lam\_wosheet, lam\_itemtype,
    > sm\_hrs, sm\_hrs\_start, sm\_hrs\_end, foilings\_reel\_no,
    > foil\_itemtype, roll\_inspected, no\_flag, wastage\_params,
    > wastage\_values, opt\_eno, line\_clearance, line\_clearance\_text,
    > checklist, checklist\_text, mr\_hrs\_start\_1, mr\_hrs\_end\_1,
    > mr\_hrs\_1, prod\_hrs\_start\_1, prod\_hrs\_end\_1, prod\_hrs\_1,
    > sm\_hrs\_1, sm\_hrs\_start\_1, sm\_hrs\_end\_1, from\_time\_1,
    > to\_time\_1, hours\_1, mr\_hrs\_start\_2, mr\_hrs\_end\_2,
    > mr\_hrs\_2, prod\_hrs\_start\_2, prod\_hrs\_end\_2, prod\_hrs\_2,
    > sm\_hrs\_2, sm\_hrs\_start\_2, sm\_hrs\_end\_2, from\_time\_2,
    > to\_time\_2, hours\_2, roll\_inspected\_date, baby\_output\_roll,
    > coli\_prefix, baby\_roll\_data

### 5.8 job\_ops (job\_operations)

-   **SELECT Columns:** op\_id, store\_id, report\_id, shift\_id,
    > operation, opt\_sort, die\_no, shiftids, order\_id

### 5.9 ph (production\_holiday)

-   **SELECT Columns:** id, store\_id, from\_date, to\_date, title

### 5.10 phd (production\_holiday\_detail)

-   **SELECT Columns:** holiday\_detail\_id, holiday\_id, store\_id,
    > date

### 5.11 holiday\_shift (holiday\_to\_shift)

-   **SELECT Columns:** id, store\_id, ref\_id, type, holiday\_id,
    > machine\_id, date, shift, from\_time, to\_time

### 5.12 store (store)

-   **SELECT Columns:** store\_id, st\_name

### 5.13 unit (production\_unit)

-   **SELECT Columns:** unit\_id, unit\_name

### 5.14 interval (operation\_interval) & schedule\_insert (smart\_schedule\_insert)

-   **SELECT Columns:** Returns all available table columns (SELECT \*).

6. Dev-Only Testing Override
----------------------------

For testing in local development environments, clients with a valid
bearer token can test requests under a different login\_id without
re-minting tokens.

-   **Condition:** Must originate from localhost (127.0.0.1 or ::1) OR
    > have environment variable AI\_AGENT\_ALLOW\_TEST\_TOKEN=1.

-   **Usage:** Include \"login\_id\" in the root request body.

{\
\"action\": \"select\",\
\"table\": \"order\",\
\"login\_id\": 110\
}

7. Error Handling & HTTP Status Codes
-------------------------------------

When an error occurs, the API returns a standard JSON structure
accompanied by a corresponding HTTP status code. Detailed internal
errors are logged internally to ai\_agent\_sso\_log.

### Error Response Format

{\
\"status\": \"error\",\
\"error\": \"Human-readable public error message\"\
}

### Common HTTP Status Codes

  **HTTP Code**      **Error Message**                                     **Common Internal Reason**
  ------------------ ----------------------------------------------------- -------------------------------------------------------------------------
  401 Unauthorized   Missing bearer token.                                 missing\_token
  401 Unauthorized   Invalid token.                                        tenant\_mismatch, wrong\_token\_purpose, missing\_jti, issuer\_mismatch
  401 Unauthorized   This token has expired.                               token\_expired
  401 Unauthorized   Your ERP session has ended.                           erp\_session\_logged\_out
  401 Unauthorized   This API key has been revoked.                        api\_key\_revoked
  403 Forbidden      Access Denied: Smart Schedule AI Agent not enabled.   integration\_disabled, inactive\_user
  400 Bad Request    Request body must be JSON.                            invalid\_json
  400 Bad Request    Table access denied.                                  table\_not\_whitelisted, table\_not\_store\_scoped
  400 Bad Request    Insert is not configured for table \"\...\".          insert\_not\_configured
  500 Server Error   Could not connect to the data source.                 tenant\_db\_connect\_failed
  500 Server Error   Query failed.                                         query\_failed
