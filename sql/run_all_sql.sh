RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Database credentials
DB_HOST="localhost"
DB_PORT="3307"
DB_USER="dwh_user"
DB_PASS="dwh_pass123"
DB_NAME="instacart_dwh"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${YELLOW}================================${NC}"
echo -e "${YELLOW}Instacart DWH Setup${NC}"
echo -e "${YELLOW}================================${NC}"
echo -e "Script dir: ${SCRIPT_DIR}"

# Check if MariaDB is running
echo -e "\n${YELLOW}[1/11] Checking MariaDB connection...${NC}"
if docker exec instacart-mariadb mariadb -uroot -proot123 -e "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ MariaDB is running${NC}"
else
    echo -e "${RED}✗ Cannot connect to MariaDB. Is the container running?${NC}"
    echo -e "${YELLOW}Try: docker start instacart-mariadb${NC}"
    exit 1
fi

# Function to execute SQL file
execute_sql() {
    local file=$1
    local description=$2
    local step=$3
    local use_root=$4
    
    echo -e "\n${YELLOW}[${step}/11] ${description}${NC}"
    echo -e "Executing: ${file}"
    
    # Check file exists
    if [ ! -f "$file" ]; then
        echo -e "${RED}✗ File not found: ${file}${NC}"
        exit 1
    fi
    
    # Execute SQL
    if [ "$use_root" = "true" ]; then
        if docker exec -i instacart-mariadb mariadb -uroot -proot123 < "$file" 2>&1 | grep -v "Warning: Using a password"; then
            echo -e "${GREEN}✓ Success${NC}"
        else
            echo -e "${RED}✗ Failed to execute ${file}${NC}"
            exit 1
        fi
    else
        if docker exec -i instacart-mariadb mariadb -u${DB_USER} -p${DB_PASS} ${DB_NAME} < "$file" 2>&1 | grep -v "Warning: Using a password"; then
            echo -e "${GREEN}✓ Success${NC}"
        else
            echo -e "${RED}✗ Failed to execute ${file}${NC}"
            exit 1
        fi
    fi
}

# Execute SQL files in order
execute_sql "01_create_database.sql" "Creating database" "2" "true"
execute_sql "02_dim_time.sql" "Creating Dim_Time (168 rows)" "3" "false"
execute_sql "03_dim_department.sql" "Creating Dim_Department" "4" "false"
execute_sql "04_dim_aisle.sql" "Creating Dim_Aisle" "5" "false"
execute_sql "05_dim_product.sql" "Creating Dim_Product" "6" "false"
execute_sql "06_dim_user.sql" "Creating Dim_User" "7" "false"
execute_sql "07_fact_orders.sql" "Creating Fact_Orders (LIST partitioned)" "8" "false"
execute_sql "08_fact_order_details.sql" "Creating Fact_Order_Details (RANGE partitioned)" "9" "false"
execute_sql "09_additional_indexes.sql" "Creating indexes" "10" "false"

echo -e "\n${YELLOW}[11/11] Verifying schema...${NC}"
docker exec instacart-mariadb mariadb -u${DB_USER} -p${DB_PASS} -D${DB_NAME} -e "SHOW TABLES;" 2>&1 | grep -v "Warning: Using a password"

echo -e "\n${YELLOW}Checking partitions...${NC}"
docker exec instacart-mariadb mariadb -u${DB_USER} -p${DB_PASS} -D${DB_NAME} -e "
SELECT TABLE_NAME, PARTITION_NAME, PARTITION_METHOD 
FROM INFORMATION_SCHEMA.PARTITIONS 
WHERE TABLE_SCHEMA = '${DB_NAME}' 
  AND PARTITION_NAME IS NOT NULL 
ORDER BY TABLE_NAME, PARTITION_ORDINAL_POSITION;
" 2>&1 | grep -v "Warning: Using a password"

echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}✓ Database schema created successfully!${NC}"
echo -e "${GREEN}================================${NC}"
echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "1. Check .env file: cat ../.env"
echo -e "2. Run ETL: cd .. && python etl/etl_pipeline.py"
echo -e "3. Run dashboard: ./run_dashboard.sh"
echo -e "4. Run mining: ./run_mining.sh all"
echo -e "2. Check partitions: mysql < sql/10_check_partitions.sql"
echo -e "3. Run maintenance: mysql < sql/11_maintenance.sql"
echo -e "4. Add indexes: mysql < sql/09_additional_indexes.sql"
