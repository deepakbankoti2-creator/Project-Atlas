<?php
defined('BASEPATH') OR exit('No direct script access allowed');

/**
 * Project Atlas — FastAPI Agent Client Library for CodeIgniter 3
 * 
 * Communicates with the Python FastAPI backend over HTTP/REST with strict timeout controls,
 * structured payload parsing, and resilient error recovery.
 */
class Atlas_client {

    protected $CI;
    protected $base_url;
    protected $timeout;
    protected $api_key;

    public function __construct($config = array()) {
        $this->CI =& get_instance();
        $this->CI->load->config('atlas', TRUE);

        $this->base_url = rtrim($this->CI->config->item('atlas_api_base_url', 'atlas') ?: 'http://localhost:8000', '/');
        $this->timeout  = (int)($this->CI->config->item('atlas_api_timeout', 'atlas') ?: 30);
        $this->api_key  = $this->CI->config->item('atlas_api_key', 'atlas') ?: 'atlas_secret_token_2025';
    }

    /**
     * Submit question to FastAPI LangGraph Agent Workflow
     * 
     * @param string $client_id Client identifier (e.g., 'C-01', 'C-02')
     * @param string $question Natural language question
     * @return array Standardized result array matching WorkflowOutput schema
     */
    public function ask($client_id, $question) {
        $endpoint = $this->base_url . '/api/v1/chat';
        $payload = array(
            'client_id' => trim($client_id),
            'question'  => trim($question),
            'top_k'     => 5
        );

        $start_time = microtime(true);
        $result = $this->_send_request('POST', $endpoint, $payload);
        $elapsed_sec = round(microtime(true) - $start_time, 2);

        if ($result['status'] === 'success') {
            $data = $result['data'];
            $data['client_id'] = $client_id;
            $data['query'] = $question;
            $data['latency_sec'] = $elapsed_sec;
            $data['is_fallback'] = false;
            return $data;
        }

        // Graceful fallback response when backend times out or errors
        log_message('error', 'Project Atlas FastAPI request failed: ' . $result['error_message']);

        return array(
            'answer' => "I am currently unable to reach the Project Atlas Copilot engine. Our team has been notified, or the request timed out beyond the 30-second budget. Please try again shortly or contact your account representative.",
            'citations' => array(),
            'confidence' => 0.0,
            'conflicts' => array(),
            'derived_values' => array(),
            'escalated' => true,
            'escalation_ticket_id' => 'ESC-TIMEOUT-' . time(),
            'route' => 'service_unavailable',
            'conversation_id' => null,
            'latency_sec' => $elapsed_sec,
            'is_fallback' => true,
            'error_detail' => $result['error_message']
        );
    }

    /**
     * Submit thumbs-up or thumbs-down rating
     * 
     * @param int $conversation_id
     * @param string $client_id
     * @param string $rating 'up' or 'down'
     * @param string|null $comment
     * @return array
     */
    public function submit_feedback($conversation_id, $client_id, $rating, $comment = null) {
        $endpoint = $this->base_url . '/api/v1/feedback';
        $payload = array(
            'conversation_id' => (int)$conversation_id,
            'client_id'       => trim($client_id),
            'rating'          => strtolower(trim($rating)),
            'comment'         => $comment ? trim($comment) : null
        );

        return $this->_send_request('POST', $endpoint, $payload);
    }

    /**
     * Fetch list of escalations
     * 
     * @return array
     */
    public function get_escalations() {
        $endpoint = $this->base_url . '/api/v1/escalations';
        $res = $this->_send_request('GET', $endpoint);
        return ($res['status'] === 'success') ? $res['data'] : array();
    }

    /**
     * Check backend health
     * 
     * @return bool
     */
    public function is_healthy() {
        $endpoint = $this->base_url . '/api/v1/health';
        $res = $this->_send_request('GET', $endpoint);
        return ($res['status'] === 'success' && isset($res['data']['status']) && $res['data']['status'] === 'healthy');
    }

    /**
     * Internal cURL executor
     */
    protected function _send_request($method, $url, $payload = null) {
        $ch = curl_init();

        $headers = array(
            'Content-Type: application/json',
            'Accept: application/json',
            'X-API-Key: ' . $this->api_key
        );

        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, TRUE);
        curl_setopt($ch, CURLOPT_TIMEOUT, $this->timeout);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, FALSE);

        if ($method === 'POST') {
            curl_setopt($ch, CURLOPT_POST, TRUE);
            if (!empty($payload)) {
                curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
            }
        }

        $raw_response = curl_exec($ch);
        $http_code    = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_error   = curl_error($ch);
        $curl_errno   = curl_errno($ch);
        curl_close($ch);

        if ($curl_errno !== 0) {
            return array(
                'status' => 'error',
                'http_code' => $http_code,
                'error_message' => "cURL Error ({$curl_errno}): {$curl_error}",
                'data' => null
            );
        }

        $decoded = json_decode($raw_response, TRUE);

        if ($http_code >= 200 && $http_code < 300) {
            return array(
                'status' => 'success',
                'http_code' => $http_code,
                'data' => $decoded,
                'error_message' => null
            );
        }

        $msg = "HTTP {$http_code}";
        if (is_array($decoded) && isset($decoded['detail'])) {
            $msg .= ": " . (is_array($decoded['detail']) ? json_encode($decoded['detail']) : $decoded['detail']);
        }

        return array(
            'status' => 'error',
            'http_code' => $http_code,
            'error_message' => $msg,
            'data' => $decoded
        );
    }
}
