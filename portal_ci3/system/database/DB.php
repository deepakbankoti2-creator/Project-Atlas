<?php
defined('BASEPATH') OR exit('No direct script access allowed');

class CI_DB {
    private static $instance = null;
    public $conn_id = null;
    public $insert_id = 0;

    protected $_where = array();
    protected $_order_by = array();
    protected $_limit = null;

    public function __construct() {
        require(APPPATH . 'config/database.php');
        $conf = isset($db['default']) ? $db['default'] : array();

        $host = isset($conf['hostname']) ? $conf['hostname'] : 'localhost';
        $port = isset($conf['port']) ? $conf['port'] : 3306;
        $user = isset($conf['username']) ? $conf['username'] : 'root';
        $pass = isset($conf['password']) ? $conf['password'] : '';
        $name = isset($conf['database']) ? $conf['database'] : 'project_atlas';

        try {
            $dsn = "mysql:host={$host};port={$port};dbname={$name};charset=utf8mb4";
            $this->conn_id = new PDO($dsn, $user, $pass, array(
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_TIMEOUT => 3
            ));
        } catch (Exception $e) {
            log_message('error', 'MySQL PDO Connection failed: ' . $e->getMessage());
            $this->conn_id = null;
        }
    }

    public static function &get_instance() {
        if (self::$instance === null) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    public function where($key, $value = NULL) {
        if (is_array($key)) {
            foreach ($key as $k => $v) { $this->_where[$k] = $v; }
        } else {
            $this->_where[$key] = $value;
        }
        return $this;
    }

    public function order_by($col, $dir = 'ASC') {
        $this->_order_by[] = "`{$col}` {$dir}";
        return $this;
    }

    public function limit($limit) {
        $this->_limit = (int)$limit;
        return $this;
    }

    public function insert($table, $data) {
        if (!$this->conn_id) return FALSE;

        $cols = array_keys($data);
        $fields = implode(', ', array_map(function($c) { return "`{$c}`"; }, $cols));
        $placeholders = implode(', ', array_fill(0, count($cols), '?'));
        $sql = "INSERT INTO `{$table}` ({$fields}) VALUES ({$placeholders})";

        $stmt = $this->conn_id->prepare($sql);
        $res = $stmt->execute(array_values($data));
        $this->insert_id = (int)$this->conn_id->lastInsertId();
        return $res;
    }

    public function insert_id() {
        return $this->insert_id;
    }

    public function get($table) {
        if (!$this->conn_id) {
            return new class {
                public function result_array() { return array(); }
                public function row_array() { return null; }
            };
        }

        $sql = "SELECT * FROM `{$table}`";
        $params = array();

        if (!empty($this->_where)) {
            $clauses = array();
            foreach ($this->_where as $col => $val) {
                $clauses[] = "`{$col}` = ?";
                $params[] = $val;
            }
            $sql .= " WHERE " . implode(' AND ', $clauses);
        }

        if (!empty($this->_order_by)) {
            $sql .= " ORDER BY " . implode(', ', $this->_order_by);
        }

        if ($this->_limit !== null) {
            $sql .= " LIMIT " . $this->_limit;
        }

        // Reset query builder
        $this->_where = array();
        $this->_order_by = array();
        $this->_limit = null;

        $stmt = $this->conn_id->prepare($sql);
        $stmt->execute($params);
        $rows = $stmt->fetchAll();

        return new class($rows) {
            private $data;
            public function __construct($data) { $this->data = $data; }
            public function result_array() { return $this->data ?: array(); }
            public function row_array() { return !empty($this->data) ? $this->data[0] : null; }
        };
    }
}
