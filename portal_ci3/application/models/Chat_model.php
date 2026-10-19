<?php
defined('BASEPATH') OR exit('No direct script access allowed');

/**
 * Chat Model for Project Atlas CI3 Portal
 * 
 * Persists conversations and user feedback in MySQL.
 */
class Chat_model extends CI_Model {

    public function __construct() {
        parent::__construct();
        // Load database safely
        $this->load->database();
    }

    /**
     * Save a completed conversation turn to MySQL
     * 
     * @param array $data
     * @return int|null Insert ID or null if DB unavailable
     */
    public function save_conversation($data) {
        if (!$this->db->conn_id) {
            return null;
        }

        try {
            $insert_data = array(
                'client_id'            => $data['client_id'],
                'question'             => $data['question'],
                'answer'               => $data['answer'],
                'citations_json'       => !empty($data['citations']) ? json_encode($data['citations']) : null,
                'confidence'           => isset($data['confidence']) ? (string)$data['confidence'] : '0.0',
                'conflicts_json'       => !empty($data['conflicts']) ? json_encode($data['conflicts']) : null,
                'derived_values_json'  => !empty($data['derived_values']) ? json_encode($data['derived_values']) : null,
                'escalated'            => !empty($data['escalated']) ? 1 : 0,
                'escalation_ticket_id' => isset($data['escalation_ticket_id']) ? $data['escalation_ticket_id'] : null,
                'route'                => isset($data['route']) ? $data['route'] : 'unknown',
                'created_at'           => date('Y-m-d H:i:s')
            );

            $this->db->insert('conversations', $insert_data);
            return $this->db->insert_id();
        } catch (Exception $e) {
            log_message('error', 'Chat_model::save_conversation failed: ' . $e->getMessage());
            return null;
        }
    }

    /**
     * Store thumbs-up or thumbs-down feedback
     * 
     * @param int $conversation_id
     * @param string $client_id
     * @param string $rating 'up' or 'down'
     * @param string|null $comment
     * @return int|null Insert ID
     */
    public function save_feedback($conversation_id, $client_id, $rating, $comment = null) {
        if (!$this->db->conn_id) {
            return null;
        }

        try {
            $insert_data = array(
                'conversation_id' => (int)$conversation_id,
                'client_id'       => $client_id,
                'rating'          => strtolower($rating) === 'up' ? 'up' : 'down',
                'comment'         => $comment ? $comment : null,
                'created_at'      => date('Y-m-d H:i:s')
            );

            $this->db->insert('feedback', $insert_data);
            return $this->db->insert_id();
        } catch (Exception $e) {
            log_message('error', 'Chat_model::save_feedback failed: ' . $e->getMessage());
            return null;
        }
    }

    /**
     * Get recent conversations for a client
     * 
     * @param string $client_id
     * @param int $limit
     * @return array
     */
    public function get_client_history($client_id, $limit = 20) {
        if (!$this->db->conn_id) {
            return array();
        }

        try {
            $this->db->where('client_id', $client_id);
            $this->db->order_by('id', 'DESC');
            $this->db->limit($limit);
            $query = $this->db->get('conversations');
            return $query->result_array();
        } catch (Exception $e) {
            log_message('error', 'Chat_model::get_client_history failed: ' . $e->getMessage());
            return array();
        }
    }

    /**
     * Fetch client info
     */
    public function get_client($client_id) {
        if (!$this->db->conn_id) {
            // Static fallback for offline demo
            $clients = array(
                'C-01' => array('id' => 'C-01', 'company' => 'Northwind Utilities', 'contact_email' => 'ops@example.com', 'purchased_reports' => 'R-101, R-103, R-104'),
                'C-02' => array('id' => 'C-02', 'company' => 'Blue Delta Infra', 'contact_email' => 'procurement@example.com', 'purchased_reports' => 'R-103, R-106')
            );
            return isset($clients[$client_id]) ? $clients[$client_id] : null;
        }

        try {
            $this->db->where('id', $client_id);
            $query = $this->db->get('clients');
            return $query->row_array();
        } catch (Exception $e) {
            return null;
        }
    }
}
