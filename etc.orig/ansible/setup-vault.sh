#!/bin/bash

# Ansible Vault Setup Script
# This script helps set up the Ansible vault for secure credential management

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_DIR="$SCRIPT_DIR/vault"
TEMPLATE_FILE="$VAULT_DIR/secrets.yml.template"
VAULT_FILE="$VAULT_DIR/secrets.yml"
VAULT_PASS_FILE="$SCRIPT_DIR/.vault_pass"

echo -e "${BLUE}=== Ansible Vault Setup Script ===${NC}"
echo

# Check if ansible-vault is available
if ! command -v ansible-vault &> /dev/null; then
    echo -e "${RED}Error: ansible-vault command not found. Please install Ansible first.${NC}"
    exit 1
fi

# Check if template exists
if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo -e "${RED}Error: Template file not found at $TEMPLATE_FILE${NC}"
    exit 1
fi

# Function to create vault file
create_vault_file() {
    echo -e "${YELLOW}Creating vault file from template...${NC}"
    
    if [[ -f "$VAULT_FILE" ]]; then
        echo -e "${YELLOW}Vault file already exists. Do you want to overwrite it? (y/N)${NC}"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo -e "${BLUE}Keeping existing vault file.${NC}"
            return 0
        fi
    fi
    
    cp "$TEMPLATE_FILE" "$VAULT_FILE"
    echo -e "${GREEN}Vault file created at $VAULT_FILE${NC}"
    echo -e "${YELLOW}Please edit this file and replace all CHANGE_ME_* values with actual secrets.${NC}"
    echo
}

# Function to edit vault file
edit_vault_file() {
    if [[ ! -f "$VAULT_FILE" ]]; then
        echo -e "${RED}Error: Vault file not found. Please create it first.${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Opening vault file for editing...${NC}"
    
    # Check if file is encrypted
    if head -n 1 "$VAULT_FILE" | grep -q "\$ANSIBLE_VAULT"; then
        echo -e "${BLUE}File is encrypted. Using ansible-vault edit...${NC}"
        ansible-vault edit "$VAULT_FILE"
    else
        echo -e "${BLUE}File is not encrypted. Opening with default editor...${NC}"
        ${EDITOR:-vim} "$VAULT_FILE"
    fi
}

# Function to encrypt vault file
encrypt_vault_file() {
    if [[ ! -f "$VAULT_FILE" ]]; then
        echo -e "${RED}Error: Vault file not found. Please create it first.${NC}"
        return 1
    fi
    
    # Check if already encrypted
    if head -n 1 "$VAULT_FILE" | grep -q "\$ANSIBLE_VAULT"; then
        echo -e "${YELLOW}Vault file is already encrypted.${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}Encrypting vault file...${NC}"
    ansible-vault encrypt "$VAULT_FILE"
    echo -e "${GREEN}Vault file encrypted successfully!${NC}"
}

# Function to create vault password file
create_vault_password_file() {
    echo -e "${YELLOW}Do you want to create a vault password file for easier access? (y/N)${NC}"
    echo -e "${RED}Warning: This will store your vault password in plain text!${NC}"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Enter your vault password:${NC}"
        read -s vault_password
        echo
        
        echo "$vault_password" > "$VAULT_PASS_FILE"
        chmod 600 "$VAULT_PASS_FILE"
        
        echo -e "${GREEN}Vault password file created at $VAULT_PASS_FILE${NC}"
        echo -e "${YELLOW}You can now use --vault-password-file .vault_pass with ansible commands${NC}"
        echo -e "${RED}Remember to add .vault_pass to your .gitignore file!${NC}"
    fi
}

# Function to test vault
test_vault() {
    if [[ ! -f "$VAULT_FILE" ]]; then
        echo -e "${RED}Error: Vault file not found.${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Testing vault file...${NC}"
    
    if head -n 1 "$VAULT_FILE" | grep -q "\$ANSIBLE_VAULT"; then
        echo -e "${BLUE}Attempting to view encrypted vault...${NC}"
        if ansible-vault view "$VAULT_FILE" > /dev/null 2>&1; then
            echo -e "${GREEN}Vault file is valid and can be decrypted!${NC}"
        else
            echo -e "${RED}Error: Cannot decrypt vault file. Check your password.${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}Vault file is not encrypted yet.${NC}"
    fi
}

# Main menu
show_menu() {
    echo -e "${BLUE}What would you like to do?${NC}"
    echo "1. Create vault file from template"
    echo "2. Edit vault file"
    echo "3. Encrypt vault file"
    echo "4. Create vault password file"
    echo "5. Test vault file"
    echo "6. Show vault status"
    echo "7. Exit"
    echo
}

# Function to show vault status
show_vault_status() {
    echo -e "${BLUE}=== Vault Status ===${NC}"
    
    if [[ -f "$VAULT_FILE" ]]; then
        if head -n 1 "$VAULT_FILE" | grep -q "\$ANSIBLE_VAULT"; then
            echo -e "Vault file: ${GREEN}EXISTS (ENCRYPTED)${NC}"
        else
            echo -e "Vault file: ${YELLOW}EXISTS (NOT ENCRYPTED)${NC}"
        fi
    else
        echo -e "Vault file: ${RED}NOT FOUND${NC}"
    fi
    
    if [[ -f "$VAULT_PASS_FILE" ]]; then
        echo -e "Password file: ${GREEN}EXISTS${NC}"
    else
        echo -e "Password file: ${RED}NOT FOUND${NC}"
    fi
    
    if [[ -f "$TEMPLATE_FILE" ]]; then
        echo -e "Template file: ${GREEN}EXISTS${NC}"
    else
        echo -e "Template file: ${RED}NOT FOUND${NC}"
    fi
    echo
}

# Main loop
while true; do
    show_vault_status
    show_menu
    
    read -p "Enter your choice (1-7): " choice
    echo
    
    case $choice in
        1)
            create_vault_file
            ;;
        2)
            edit_vault_file
            ;;
        3)
            encrypt_vault_file
            ;;
        4)
            create_vault_password_file
            ;;
        5)
            test_vault
            ;;
        6)
            # Status is shown at the top of the loop
            continue
            ;;
        7)
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice. Please try again.${NC}"
            ;;
    esac
    
    echo
    echo -e "${BLUE}Press Enter to continue...${NC}"
    read
    clear
done