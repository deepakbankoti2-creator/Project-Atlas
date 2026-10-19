<?php
defined('BASEPATH') OR exit('No direct script access allowed');

/**
 * Chat Controller for Project Atlas CI3 Portal
 * 
 * Provides web UI and AJAX endpoints for the Report Copilot chat experience,
 * including client switching, interactive feedback, XSS escaping, and CSRF protection.
 */
class Chat extends CI_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->library('session');
        $this->load->library('atlas_client');
        $this->load->model('chat_model');
        $this->load->helper(array('url', 'form', 'security', 'html'));
    }

    /**
     * Main Chat Interface View
     */
    public function index() {
        $active_client_id = $this->session->userdata('active_client_id') ?: 'C-01';
        $client_info = $this->chat_model->get_client($active_client_id);
        $history = $this->chat_model->get_client_history($active_client_id, 15);

        $data = array(
            'page_title'       => 'Project Atlas — Report Copilot',
            'active_client_id' => $active_client_id,
            'client_info'      => $client_info,
            'history'          => $history,
            'backend_healthy'  => $this->atlas_client->is_healthy(),
            'csrf_name'        => $this->security->get_csrf_token_name(),
            'csrf_hash'        => $this->security->get_csrf_hash()
        );

        $this->load->view('chat_view', $data);
    }

    /**
     * AJAX endpoint to submit a query to the Copilot
     */
    public function ask() {
        // Enforce POST request
        if ($this->input->method() !== 'post') {
            return $this->_json_response(array('error' => 'Method not allowed'), 405);
        }

        // Security Requirement 9: Do not trust a client ID submitted by the browser as proof of authorization.
        // Validate the authenticated user's permitted client identity strictly from server-side session context.
        $session_client_id = $this->session->userdata('active_client_id') ?: 'C-01';
        $allowed_clients   = array('C-01', 'C-02');
        if (!in_array($session_client_id, $allowed_clients)) {
            $session_client_id = 'C-01';
            $this->session->set_userdata('active_client_id', 'C-01');
        }
        $client_id = $session_client_id;
        $question  = $this->input->post('question', TRUE);

        if (empty(trim($question))) {
            return $this->_json_response(array('error' => 'Question cannot be empty.'), 400);
        }

        // Call FastAPI Agent backend
        $copilot_result = $this->atlas_client->ask($client_id, $question);

        // Persist to MySQL
        $db_conv_data = array(
            'client_id'            => $client_id,
            'question'             => $question,
            'answer'               => $copilot_result['answer'],
            'citations'            => isset($copilot_result['citations']) ? $copilot_result['citations'] : array(),
            'confidence'           => isset($copilot_result['confidence']) ? $copilot_result['confidence'] : 0.0,
            'conflicts'            => isset($copilot_result['conflicts']) ? $copilot_result['conflicts'] : array(),
            'derived_values'       => isset($copilot_result['derived_values']) ? $copilot_result['derived_values'] : array(),
            'escalated'            => isset($copilot_result['escalated']) ? $copilot_result['escalated'] : false,
            'escalation_ticket_id' => isset($copilot_result['escalation_ticket_id']) ? $copilot_result['escalation_ticket_id'] : null,
            'route'                => isset($copilot_result['route']) ? $copilot_result['route'] : 'unknown'
        );

        $conv_id = $this->chat_model->save_conversation($db_conv_data);
        if ($conv_id) {
            $copilot_result['conversation_id'] = $conv_id;
        }

        // Return JSON with refreshed CSRF token for seamless AJAX
        $copilot_result['csrf_name'] = $this->security->get_csrf_token_name();
        $copilot_result['csrf_hash'] = $this->security->get_csrf_hash();

        return $this->_json_response($copilot_result);
    }

    /**
     * AJAX endpoint to submit thumbs up / down feedback
     */
    public function feedback() {
        if ($this->input->method() !== 'post') {
            return $this->_json_response(array('error' => 'Method not allowed'), 405);
        }

        $conv_id   = (int)$this->input->post('conversation_id', TRUE);
        $client_id = $this->input->post('client_id', TRUE) ?: 'C-01';
        $rating    = $this->input->post('rating', TRUE);
        $comment   = $this->input->post('comment', TRUE);

        if (!in_array(strtolower($rating), array('up', 'down'))) {
            return $this->_json_response(array('error' => 'Invalid rating value.'), 400);
        }

        // Save locally in MySQL
        $this->chat_model->save_feedback($conv_id, $client_id, $rating, $comment);

        // Also notify backend API service
        $this->atlas_client->submit_feedback($conv_id, $client_id, $rating, $comment);

        return $this->_json_response(array(
            'status' => 'success',
            'message' => 'Thank you for your feedback!',
            'csrf_name' => $this->security->get_csrf_token_name(),
            'csrf_hash' => $this->security->get_csrf_hash()
        ));
    }

    /**
     * Switch current enterprise client identity (C-01 or C-02)
     */
    public function switch_client($client_id) {
        $allowed = array('C-01', 'C-02');
        if (in_array($client_id, $allowed)) {
            $this->session->set_userdata('active_client_id', $client_id);
        }
        redirect('chat');
    }

    /**
     * Helper to render JSON responses with correct HTTP headers
     */
    protected function _json_response($data, $status_code = 200) {
        $this->output
             ->set_status_header($status_code)
             ->set_content_type('application/json', 'utf-8')
             ->set_output(json_encode($data));
    }
}
