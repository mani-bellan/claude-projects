Build a Cortex Analyst semantic model YAML for the table or domain described in $ARGUMENTS.

Follow the Cortex Analyst semantic model spec:

```yaml
name: <model_name>
description: <one-line description>

tables:
  - name: <physical_table>
    base_table:
      database: <db>
      schema: <schema>
      table: <table>
    description: <what this table represents>

    dimensions:
      - name: <dim_name>
        expr: <column_or_expression>
        data_type: TEXT | DATE | TIMESTAMP | BOOLEAN
        description: <business meaning>
        sample_values: [value1, value2, value3]

    time_dimensions:
      - name: <time_dim_name>
        expr: <date_column>
        data_type: DATE | TIMESTAMP
        description: <when this event happened>

    measures:
      - name: <measure_name>
        expr: <column_or_expression>
        data_type: NUMBER
        default_aggregation: sum | avg | count | min | max
        description: <business meaning>
```

Then generate:
1. The complete YAML for the described table/domain
2. A Python snippet to upload the YAML to a Snowflake stage and call the Cortex Analyst REST API (`/api/v2/cortex/analyst/message`) with a sample natural-language question
3. Three example NL questions a business user might ask, with the expected SQL Cortex Analyst would generate
